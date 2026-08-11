from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.public import masked_address, record_visit
from app.database.base import Base
from app.models.dashboard import WebsiteVisit


def test_addresses_are_reduced_to_networks() -> None:
    assert masked_address("8.8.8.42") == "8.8.8.0/24"
    assert masked_address("2001:4860:4860:1234::1") == "2001:4860:4860:1234::/64"
    assert masked_address("invalid") == "unbekannt"


def test_same_address_is_aggregated_without_storing_full_ip() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    request = SimpleNamespace(headers={"x-forwarded-for": "8.8.8.42", "user-agent": "Testbrowser"}, client=None)
    with Session(engine) as db:
        assert record_visit(request, db).media_type == "image/gif"
        record_visit(request, db)
        item = db.scalar(select(WebsiteVisit))
        assert item.masked_ip == "8.8.8.0/24"
        assert item.views == 2
        assert "203.0.113.42" not in item.visitor_hash
