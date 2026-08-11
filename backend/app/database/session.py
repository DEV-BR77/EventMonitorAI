from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from app.core.config import settings
from app.database.tenancy import TenantScopedMixin

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


@event.listens_for(Session, "do_orm_execute")
def _isolate_tenant_reads(execute_state) -> None:
    tenant_id = execute_state.session.info.get("tenant_id")
    if tenant_id is None or execute_state.execution_options.get("include_all_tenants"):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantScopedMixin,
            lambda model: model.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _assign_tenant_to_new_rows(session: Session, _flush_context, _instances) -> None:
    tenant_id = session.info.get("tenant_id")
    if tenant_id is None:
        return
    for item in session.new:
        if isinstance(item, TenantScopedMixin):
            item.tenant_id = tenant_id


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
