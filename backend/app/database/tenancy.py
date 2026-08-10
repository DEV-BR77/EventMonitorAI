from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column


DEFAULT_TENANT_ID = 1


class TenantScopedMixin:
    """Marker and column used by the session-wide tenant isolation policy."""

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        default=DEFAULT_TENANT_ID,
        index=True,
    )
