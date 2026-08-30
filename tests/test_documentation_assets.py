import base64
from pathlib import Path

import pytest
from app.api.documentation import asset_file, list_assets, list_categories, upload_asset
from app.core.config import settings
from app.database.base import Base
from app.models.dashboard import User
from app.schemas.dashboard import DocumentationAssetUpload
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _image_payload(title: str = "Müllplatz") -> DocumentationAssetUpload:
    return DocumentationAssetUpload(
        kind="image",
        title=title,
        category="Müll",
        occurred_at="2026-08-31T12:30:00",
        filename="nachweis.jpg",
        mime_type="image/jpeg",
        content_base64=base64.b64encode(b"\xff\xd8\xfftest-image").decode(),
    )


def test_documentation_upload_is_stored_and_tenant_isolated(tmp_path: Path) -> None:
    original = settings.documentation_directory
    settings.documentation_directory = str(tmp_path)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            db.info["tenant_id"] = 1
            created = upload_asset(_image_payload(), db, User(username="user@example.com", password_hash="x", role="viewer"))
            assert created.tenant_id == 1
            assert Path(created.stored_path).read_bytes().startswith(b"\xff\xd8\xff")
            assert [item.id for item in list_assets(db, User(), kind="image")] == [created.id]
            assert list_categories(db, User(), kind="image") == ["Müll"]
            assert asset_file(created.id, db, User()).media_type == "image/jpeg"

            db.info["tenant_id"] = 2
            assert list_assets(db, User(), kind="image") == []
            assert list_categories(db, User(), kind="image") == []
            with pytest.raises(HTTPException) as error:
                asset_file(created.id, db, User())
            assert error.value.status_code == 404
    finally:
        settings.documentation_directory = original


def test_documentation_rejects_spoofed_file_type(tmp_path: Path) -> None:
    original = settings.documentation_directory
    settings.documentation_directory = str(tmp_path)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    data = _image_payload("Falsche Datei")
    data.content_base64 = base64.b64encode(b"not-a-jpeg").decode()
    try:
        with Session(engine) as db:
            db.info["tenant_id"] = 1
            with pytest.raises(HTTPException) as error:
                upload_asset(data, db, User(username="user@example.com", password_hash="x", role="viewer"))
            assert error.value.status_code == 415
    finally:
        settings.documentation_directory = original
