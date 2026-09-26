from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo


Period = Literal["daily", "weekly", "monthly", "lifetime"]


@dataclass(frozen=True)
class PeriodWindow:
    start_utc: datetime
    end_utc: datetime | None
    reset_at_utc: datetime | None


def period_window(
    period: Period,
    now: datetime,
    timezone_name: str = "Europe/Berlin",
) -> PeriodWindow:
    if period not in ("daily", "weekly", "monthly", "lifetime"):
        raise ValueError("unsupported period")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if period == "lifetime":
        return PeriodWindow(datetime.min.replace(tzinfo=timezone.utc), None, None)

    zone = ZoneInfo(timezone_name)
    local_now = now.astimezone(zone)
    local_date = local_now.date()
    if period == "daily":
        start_date = local_date
        end_date = local_date + timedelta(days=1)
    elif period == "weekly":
        start_date = local_date - timedelta(days=local_date.weekday())
        end_date = start_date + timedelta(days=7)
    else:
        start_date = local_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)

    start_local = datetime.combine(start_date, time.min, tzinfo=zone)
    end_local = datetime.combine(end_date, time.min, tzinfo=zone)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return PeriodWindow(start_utc, end_utc, end_utc)
