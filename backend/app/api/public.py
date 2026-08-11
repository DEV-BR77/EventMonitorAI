import hashlib
import hmac
import ipaddress
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.dashboard import WebsiteVisit

router = APIRouter(prefix="/public", tags=["Public"])
TRANSPARENT_GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


def masked_address(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
        if address.is_private or address.is_loopback:
            return "Docker-Gateway (Quell-IP verborgen)"
        prefix = 24 if address.version == 4 else 64
        network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
        return f"{network.network_address}/{prefix}"
    except ValueError:
        return "unbekannt"


@router.get("/visit.gif", include_in_schema=False)
def record_visit(request: Request, db: Session = Depends(get_db)) -> Response:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    remote = forwarded or (request.client.host if request.client else "unbekannt")
    browser_hint = request.headers.get("user-agent", "")[:300]
    now = datetime.now(UTC)
    visit_date = now.date().isoformat()
    digest = hmac.new(settings.auth_secret.encode(), f"{visit_date}:{remote}:{browser_hint}".encode(), hashlib.sha256).hexdigest()
    item = db.scalar(select(WebsiteVisit).where(WebsiteVisit.visit_date == visit_date, WebsiteVisit.visitor_hash == digest))
    if item is None:
        db.add(WebsiteVisit(visit_date=visit_date, visitor_hash=digest, masked_ip=masked_address(remote), first_seen_at=now.isoformat(), last_seen_at=now.isoformat()))
    else:
        item.views += 1
        item.last_seen_at = now.isoformat()
    db.commit()
    return Response(content=TRANSPARENT_GIF, media_type="image/gif", headers={"Cache-Control": "no-store, max-age=0"})
