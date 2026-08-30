from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session, noload

from app.database.base import Base
from app.database.session import engine
from app.models import Event
from app.models.dashboard import Tenant, TenantMembership, TenantSubscription, User
from app.services.label_translation import translate_label
from app.services.taxonomy import base_class_for_detection, seed_event_classes


def add_missing_event_columns() -> None:
    inspector = inspect(engine)

    if "events" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("events")}

    statements: list[str] = []

    if "label_de" not in column_names:
        statements.append("ALTER TABLE events " "ADD COLUMN label_de VARCHAR NOT NULL DEFAULT ''")

    if "category" not in column_names:
        statements.append(
            "ALTER TABLE events " "ADD COLUMN category VARCHAR NOT NULL DEFAULT 'OTHER'"
        )

    if "end_timestamp" not in column_names:
        statements.append("ALTER TABLE events " "ADD COLUMN end_timestamp VARCHAR")

    if "duration_seconds" not in column_names:
        statements.append(
            "ALTER TABLE events " "ADD COLUMN duration_seconds FLOAT NOT NULL DEFAULT 0.975"
        )

    if "avg_db_level" not in column_names:
        statements.append("ALTER TABLE events " "ADD COLUMN avg_db_level FLOAT")

    for name, definition in (
        ("primary_class_code", "VARCHAR(80)"),
        ("subclass_code", "VARCHAR(80)"),
        ("classification_status", "VARCHAR(20) NOT NULL DEFAULT 'automatic'"),
        ("corrected_by", "VARCHAR(80)"),
        ("corrected_at", "VARCHAR"),
        ("display_suppressed", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("person_monitoring_excluded", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("assessment_excluded", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("assessment_exclusion_reason", "VARCHAR(80)"),
        ("primary_learning_approved", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ):
        if name not in column_names:
            statements.append(f"ALTER TABLE events ADD COLUMN {name} {definition}")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def ensure_telemetry_counter_capacity() -> None:
    inspector = inspect(engine)
    if "device_telemetry" not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns("device_telemetry")}
    with engine.begin() as connection:
        if "db_level" not in column_names:
            connection.execute(
                text("ALTER TABLE device_telemetry ADD COLUMN db_level FLOAT NOT NULL DEFAULT 0")
            )
        if engine.dialect.name == "postgresql":
            for column in ("uptime_ms", "packets_received", "packets_lost"):
                connection.execute(
                    text(f"ALTER TABLE device_telemetry ALTER COLUMN {column} TYPE BIGINT")
                )


def ensure_device_position_columns() -> None:
    inspector = inspect(engine)
    if "devices" not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns("devices")}
    with engine.begin() as connection:
        for column in ("position_x", "position_y"):
            if column not in column_names:
                connection.execute(text(f"ALTER TABLE devices ADD COLUMN {column} FLOAT"))


def ensure_calibration_columns() -> None:
    inspector = inspect(engine)
    if "device_calibrations" not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns("device_calibrations")}
    definitions = {
        "applied_offset_db": "FLOAT NOT NULL DEFAULT 0",
        "reference_points": "INTEGER NOT NULL DEFAULT 0",
        "reference_mae_db": "FLOAT",
    }
    with engine.begin() as connection:
        for column, definition in definitions.items():
            if column not in column_names:
                connection.execute(
                    text(f"ALTER TABLE device_calibrations ADD COLUMN {column} {definition}")
                )


def ensure_event_class_visibility_column() -> None:
    inspector = inspect(engine)
    if "event_classes" not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns("event_classes")}
    if "hidden_by_default" not in column_names:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE event_classes ADD COLUMN "
                    "hidden_by_default BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )


def ensure_assessment_class_rules_column() -> None:
    inspector = inspect(engine)
    if "assessment_config" not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns("assessment_config")}
    definitions = {
        "class_rules_json": "TEXT NOT NULL DEFAULT '{}'",
        "reference_rules_json": "TEXT NOT NULL DEFAULT 'null'",
        "sensitive_periods_json": "TEXT NOT NULL DEFAULT 'null'",
    }
    with engine.begin() as connection:
        for column, definition in definitions.items():
            if column not in column_names:
                connection.execute(
                    text(f"ALTER TABLE assessment_config ADD COLUMN {column} {definition}")
                )


def ensure_classification_revision_columns() -> None:
    inspector = inspect(engine)
    if "event_classification_revisions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("event_classification_revisions")}
    with engine.begin() as connection:
        for name in ("secondary_class_codes_json", "learning_approved_codes_json"):
            if name not in columns:
                connection.execute(text(f"ALTER TABLE event_classification_revisions ADD COLUMN {name} TEXT NOT NULL DEFAULT '[]'"))


def ensure_speaker_review_columns() -> None:
    inspector = inspect(engine)
    if "event_speaker_clusters" not in inspector.get_table_names():
        return
    column_names = {
        column["name"] for column in inspector.get_columns("event_speaker_clusters")
    }
    definitions = {
        "review_status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "reviewed_by": "VARCHAR(80)",
        "reviewed_at": "VARCHAR",
    }
    with engine.begin() as connection:
        for column, definition in definitions.items():
            if column not in column_names:
                connection.execute(
                    text(f"ALTER TABLE event_speaker_clusters ADD COLUMN {column} {definition}")
                )


def ensure_person_media_columns() -> None:
    inspector = inspect(engine)
    if "person_profiles" not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns("person_profiles")}
    definitions = {
        "monitoring_enabled": "BOOLEAN NOT NULL DEFAULT TRUE",
        "photo_path": "TEXT",
        "video_path": "TEXT",
        "video_audio_path": "TEXT",
        "video_voice_similarity": "FLOAT",
        "video_voice_cluster_id": "INTEGER REFERENCES speaker_clusters(id) ON DELETE SET NULL",
    }
    with engine.begin() as connection:
        for column, definition in definitions.items():
            if column not in column_names:
                connection.execute(
                    text(f"ALTER TABLE person_profiles ADD COLUMN {column} {definition}")
                )


def seed_default_tenant() -> None:
    with Session(engine) as db:
        tenant = db.get(Tenant, 1)
        if tenant is None:
            tenant = Tenant(id=1, name="EventMonitorAI", slug="eventmonitorai")
            db.add(tenant)
            db.flush()
        if db.scalar(select(TenantSubscription).where(TenantSubscription.tenant_id == 1)) is None:
            db.add(TenantSubscription(tenant_id=1, plan="self_hosted", status="active", max_devices=10))
        existing_users = list(db.scalars(select(User)))
        memberships = set(db.scalars(select(TenantMembership.user_id).where(TenantMembership.tenant_id == 1)))
        db.add_all(TenantMembership(tenant_id=1, user_id=user.id, role=user.role) for user in existing_users if user.id not in memberships)
        db.commit()


def ensure_tenant_columns() -> None:
    inspector = inspect(engine)
    scoped_tables = {
        "events", "devices", "device_telemetry", "device_level_samples",
        "device_calibrations", "calibration_reference_runs",
        "calibration_reference_results", "live_audio_access", "push_subscriptions",
        "event_witness_responses", "ignored_detection_patterns",
        "event_classification_revisions", "audio_clips", "review_runs",
        "assessment_config", "person_profiles", "event_person_assignments",
        "speaker_clusters", "event_speaker_clusters", "notification_rules",
        "event_secondary_classifications", "speaker_analysis_runs",
    }
    with engine.begin() as connection:
        for table in sorted(scoped_tables & set(inspector.get_table_names())):
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "tenant_id" not in columns:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER NOT NULL DEFAULT 1"))


def ensure_tenant_unique_constraints() -> None:
    """Replace legacy global name uniqueness with per-customer uniqueness."""
    if engine.dialect.name != "postgresql":
        return
    inspector = inspect(engine)
    targets = {
        "person_profiles": "name",
        "speaker_clusters": "name",
        "ignored_detection_patterns": "label_normalized",
    }
    quote = engine.dialect.identifier_preparer.quote
    with engine.begin() as connection:
        for table, column in targets.items():
            if table not in inspector.get_table_names():
                continue
            constraints = inspector.get_unique_constraints(table)
            for constraint in constraints:
                if constraint.get("column_names") == [column] and constraint.get("name"):
                    connection.execute(
                        text(
                            f"ALTER TABLE {quote(table)} DROP CONSTRAINT "
                            f"{quote(constraint['name'])}"
                        )
                    )
            index_name = f"uq_{table}_tenant_{column}"
            indexes = {item["name"] for item in inspector.get_indexes(table)}
            if index_name not in indexes:
                connection.execute(
                    text(
                        f"CREATE UNIQUE INDEX {quote(index_name)} ON {quote(table)} "
                        f"(tenant_id, {quote(column)})"
                    )
                )


def backfill_events() -> None:
    with Session(engine) as db:
        events = list(db.scalars(select(Event).options(noload("*"))).all())
        changed = False

        for event in events:
            translated_label, translated_category = translate_label(
                event.label,
                event.device,
            )

            if event.label_de != translated_label or event.category != translated_category:
                event.label_de = translated_label
                event.category = translated_category
                changed = True

            if event.end_timestamp is None:
                event.end_timestamp = event.timestamp
                changed = True

            if event.duration_seconds is None:
                event.duration_seconds = 0.975
                changed = True

            if event.avg_db_level is None:
                event.avg_db_level = event.db_level
                changed = True

            if event.primary_class_code is None:
                mapped_class = base_class_for_detection(event.label, event.category)
                if mapped_class is not None:
                    event.primary_class_code = mapped_class
                    changed = True

        if changed:
            db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    seed_default_tenant()
    ensure_tenant_columns()
    ensure_tenant_unique_constraints()
    ensure_telemetry_counter_capacity()
    ensure_device_position_columns()
    ensure_calibration_columns()
    ensure_event_class_visibility_column()
    ensure_assessment_class_rules_column()
    ensure_classification_revision_columns()
    ensure_speaker_review_columns()
    ensure_person_media_columns()
    add_missing_event_columns()
    with Session(engine) as db:
        seed_event_classes(db)
    backfill_events()
