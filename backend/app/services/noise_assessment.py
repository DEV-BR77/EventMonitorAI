import json
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")

DEFAULT_REFERENCE_RULES = [
    {"name": "Nacht", "period": "night", "start_time": "00:00", "end_time": "06:00", "reference_db": 35.0},
    {"name": "Tag", "period": "day", "start_time": "06:00", "end_time": "19:00", "reference_db": 50.0},
    {"name": "Abend", "period": "evening", "start_time": "19:00", "end_time": "22:00", "reference_db": 35.0},
    {"name": "Nacht", "period": "night", "start_time": "22:00", "end_time": "00:00", "reference_db": 35.0},
]

DEFAULT_SENSITIVE_PERIODS = [
    {"name": "Werktags früh", "start_time": "06:00", "end_time": "07:00", "weekdays": [0, 1, 2, 3, 4], "include_holidays": False},
    {"name": "Werktags abends", "start_time": "20:00", "end_time": "22:00", "weekdays": [0, 1, 2, 3, 4], "include_holidays": False},
    {"name": "Sonn-/Feiertag früh", "start_time": "06:00", "end_time": "09:00", "weekdays": [6], "include_holidays": True},
    {"name": "Sonn-/Feiertag mittags", "start_time": "13:00", "end_time": "15:00", "weekdays": [6], "include_holidays": True},
    {"name": "Sonn-/Feiertag abends", "start_time": "20:00", "end_time": "22:00", "weekdays": [6], "include_holidays": True},
]


def easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    month = (h + i - e - k + 114) // 31
    day = (h + i - e - k + 114) % 31 + 1
    return date(year, month, day)


def is_national_holiday(day: date) -> bool:
    easter = easter_sunday(day.year)
    fixed = {(1, 1), (5, 1), (10, 3), (12, 25), (12, 26)}
    movable = {
        easter - timedelta(days=2),
        easter + timedelta(days=1),
        easter + timedelta(days=39),
        easter + timedelta(days=50),
    }
    return (day.month, day.day) in fixed or day in movable


def _clock(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":", 1))
    return time(hour, minute)


def _inside(clock: time, start: str, end: str) -> bool:
    lower, upper = _clock(start), _clock(end)
    if lower == upper:
        return True
    if lower < upper:
        return lower <= clock < upper
    return clock >= lower or clock < upper


def _rules(value: str | list[dict[str, Any]] | None, defaults: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = None
    return value if isinstance(value, list) else defaults


def assessment_for(
    timestamp: str,
    db_level: float,
    sensitive_surcharge_db: float = 6.0,
    apply_surcharge: bool = True,
    reference_rules: str | list[dict[str, Any]] | None = None,
    sensitive_periods: str | list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=BERLIN)
    local = instant.astimezone(BERLIN)
    clock = local.time()
    reference_rule = next(
        (
            rule
            for rule in _rules(reference_rules, DEFAULT_REFERENCE_RULES)
            if _inside(clock, str(rule["start_time"]), str(rule["end_time"]))
        ),
        DEFAULT_REFERENCE_RULES[0],
    )
    period = str(reference_rule.get("period") or reference_rule.get("name") or "Zeitregel")
    reference = float(reference_rule["reference_db"])

    holiday = is_national_holiday(local.date())
    sensitive = any(
        _inside(clock, str(rule["start_time"]), str(rule["end_time"]))
        and (
            bool(rule.get("include_holidays"))
            if holiday
            else local.weekday() in rule.get("weekdays", [])
        )
        for rule in _rules(sensitive_periods, DEFAULT_SENSITIVE_PERIODS)
    )
    surcharge = sensitive_surcharge_db if sensitive else 0.0
    applied_surcharge = surcharge if apply_surcharge else 0.0
    assessed = round(db_level + applied_surcharge, 1)
    return {
        "period": period,
        "reference_db": reference,
        "surcharge_db": surcharge,
        "surcharge_applied": apply_surcharge,
        "assessed_db": assessed,
        "exceeded": assessed > reference,
        "local_timestamp": local.isoformat(),
    }


def assessment_for_config(timestamp: str, db_level: float, config: Any) -> dict[str, object]:
    return assessment_for(
        timestamp,
        db_level,
        float(config.sensitive_surcharge_db),
        bool(config.apply_to_live),
        getattr(config, "reference_rules_json", None),
        getattr(config, "sensitive_periods_json", None),
    )
