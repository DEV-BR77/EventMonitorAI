from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")


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


def assessment_for(timestamp: str, db_level: float) -> dict[str, object]:
    instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=BERLIN)
    local = instant.astimezone(BERLIN)
    clock = local.time()
    if time(6) <= clock < time(19):
        period, reference = "day", 50.0
    elif time(19) <= clock < time(22):
        period, reference = "evening", 35.0
    else:
        period, reference = "night", 35.0

    sensitive_day = local.weekday() == 6 or is_national_holiday(local.date())
    if sensitive_day:
        sensitive = (
            time(6) <= clock < time(9)
            or time(13) <= clock < time(15)
            or time(20) <= clock < time(22)
        )
    else:
        sensitive = local.weekday() < 5 and (
            time(6) <= clock < time(7) or time(20) <= clock < time(22)
        )
    surcharge = 6.0 if sensitive else 0.0
    assessed = round(db_level + surcharge, 1)
    return {
        "period": period,
        "reference_db": reference,
        "surcharge_db": surcharge,
        "assessed_db": assessed,
        "exceeded": assessed > reference,
        "local_timestamp": local.isoformat(),
    }
