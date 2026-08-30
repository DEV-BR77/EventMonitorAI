import base64
import binascii
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import CurrentUser, require_roles
from app.database.session import get_db
from app.models.dashboard import DocumentationAsset, User
from app.schemas.dashboard import DocumentationAssetRead, DocumentationAssetUpload

router = APIRouter(prefix="/api/documentation", tags=["Documentation"])
DatabaseSession = Annotated[Session, Depends(get_db)]

ALLOWED_TYPES = {
    "image": {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"},
    "document": {"application/pdf": ".pdf"},
}
MAX_BYTES = {"image": 15 * 1024 * 1024, "document": 25 * 1024 * 1024}
BERLIN = ZoneInfo("Europe/Berlin")


def _valid_signature(kind: str, content_type: str, payload: bytes) -> bool:
    if kind == "document":
        return content_type == "application/pdf" and payload.startswith(b"%PDF-")
    return (
        (content_type == "image/jpeg" and payload.startswith(b"\xff\xd8\xff"))
        or (content_type == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n"))
        or (
            content_type == "image/webp"
            and len(payload) >= 12
            and payload[:4] == b"RIFF"
            and payload[8:12] == b"WEBP"
        )
    )


def _asset_path(asset: DocumentationAsset) -> Path:
    root = Path(settings.documentation_directory).resolve()
    path = Path(asset.stored_path).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return path


def _local_day_boundary(value: str, *, following_day: bool = False) -> str:
    try:
        boundary = datetime.fromisoformat(f"{value}T00:00:00").replace(tzinfo=BERLIN)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Ungültiger Datumsfilter") from exc
    if following_day:
        boundary += timedelta(days=1)
    return boundary.astimezone(UTC).isoformat()


@router.get("/categories", response_model=list[str])
def list_categories(
    db: DatabaseSession,
    _: CurrentUser,
    kind: Literal["image", "document"],
) -> list[str]:
    return list(
        db.scalars(
            select(DocumentationAsset.category)
            .where(DocumentationAsset.kind == kind)
            .distinct()
            .order_by(DocumentationAsset.category)
        )
    )


@router.get("/assets", response_model=list[DocumentationAssetRead])
def list_assets(
    db: DatabaseSession,
    _: CurrentUser,
    kind: Literal["image", "document"] | None = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[DocumentationAsset]:
    query = select(DocumentationAsset)
    if kind:
        query = query.where(DocumentationAsset.kind == kind)
    if category:
        query = query.where(DocumentationAsset.category == category)
    if date_from:
        query = query.where(DocumentationAsset.occurred_at >= _local_day_boundary(date_from))
    if date_to:
        query = query.where(DocumentationAsset.occurred_at < _local_day_boundary(date_to, following_day=True))
    return list(db.scalars(query.order_by(DocumentationAsset.occurred_at.desc(), DocumentationAsset.id.desc()).limit(1000)))


@router.post("/assets", response_model=DocumentationAssetRead, status_code=status.HTTP_201_CREATED)
def upload_asset(
    data: DocumentationAssetUpload,
    db: DatabaseSession,
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> DocumentationAsset:
    allowed = ALLOWED_TYPES[data.kind]
    if data.mime_type not in allowed:
        raise HTTPException(status_code=415, detail="Nicht unterstütztes Dateiformat")
    try:
        payload = base64.b64decode(data.content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=400, detail="Datei ist nicht gültig kodiert") from exc
    if not payload or len(payload) > MAX_BYTES[data.kind]:
        raise HTTPException(status_code=413, detail="Datei ist leer oder zu groß")
    if not _valid_signature(data.kind, data.mime_type, payload):
        raise HTTPException(status_code=415, detail="Dateiinhalt stimmt nicht mit dem Format überein")

    try:
        occurred = datetime.fromisoformat(data.occurred_at) if data.occurred_at else datetime.now(UTC)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Ungültiger Aufnahmezeitpunkt") from exc
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=BERLIN)

    tenant_id = int(db.info["tenant_id"])
    directory = Path(settings.documentation_directory) / str(tenant_id) / data.kind
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid4().hex}{allowed[data.mime_type]}"
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(target)
        asset = DocumentationAsset(
            kind=data.kind,
            title=data.title.strip(),
            category=data.category.strip(),
            occurred_at=occurred.astimezone(UTC).isoformat(),
            original_filename=Path(data.filename).name,
            stored_path=str(target),
            content_type=data.mime_type,
            size_bytes=len(payload),
            uploaded_by=user.username,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset
    except Exception:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise


@router.get("/assets/{asset_id}/file")
def asset_file(asset_id: int, db: DatabaseSession, _: CurrentUser) -> FileResponse:
    asset = db.scalar(
        select(DocumentationAsset).where(
            DocumentationAsset.id == asset_id,
            DocumentationAsset.tenant_id == db.info["tenant_id"],
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Nachweis nicht gefunden")
    disposition = "inline" if asset.kind == "image" else "attachment"
    return FileResponse(
        _asset_path(asset),
        media_type=asset.content_type,
        filename=asset.original_filename,
        content_disposition_type=disposition,
    )


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: int,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> None:
    asset = db.scalar(
        select(DocumentationAsset).where(
            DocumentationAsset.id == asset_id,
            DocumentationAsset.tenant_id == db.info["tenant_id"],
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Nachweis nicht gefunden")
    path = _asset_path(asset)
    db.delete(asset)
    db.commit()
    path.unlink(missing_ok=True)
