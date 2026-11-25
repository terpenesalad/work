"""Pure pay calculations for Work Counter (no UI, easy to test)."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta

PERIOD_DAYS = 14  # paid fortnightly


def _parse_hhmm(text: str) -> time:
    h, m = text.strip().split(":")
    return time(int(h), int(m))


def is_counted(day: date, cfg: dict) -> bool:
    """True if this day counts as a worked shift (default work day, unless overridden)."""
    override = cfg.get("overrides", {}).get(day.isoformat())
    if override is not None:
        return bool(override)
    return day.weekday() in cfg["workdays"]


def is_default_workday(day: date, cfg: dict) -> bool:
    return day.weekday() in cfg["workdays"]


def _shift(day: date, cfg: dict) -> tuple[datetime, datetime, datetime, datetime]:
    """(start, end, break_start, break_end) for `day`; the break is clipped to the shift."""
    start = datetime.combine(day, _parse_hhmm(cfg["start"]))
    end = datetime.combine(day, _parse_hhmm(cfg["end"]))
    b_start = datetime.combine(day, _parse_hhmm(cfg.get("break_start", "12:00")))
    b_end = b_start + timedelta(minutes=cfg.get("break_minutes", 0))
    b_start, b_end = max(b_start, start), min(b_end, end)
    if b_end < b_start:
        b_end = b_start
    return start, end, b_start, b_end


def paid_hours(cfg: dict) -> float:
    """Paid hours in a shift: start to finish, minus the unpaid break."""
    start, end, b_start, b_end = _shift(date(2000, 1, 3), cfg)
    return max(0.0, ((end - start) - (b_end - b_start)).total_seconds() / 3600)


def paid_seconds(now: datetime, cfg: dict) -> float:
    """Paid seconds worked so far today. Only runs between start and finish,
    and pauses for the unpaid break."""
    start, end, b_start, b_end = _shift(now.date(), cfg)

    def upto(a: datetime, b: datetime) -> float:
        return max(0.0, (min(now, b) - a).total_seconds())

    return max(0.0, upto(start, end) - upto(b_start, b_end))


def floor_cents(value: float) -> float:
    return math.floor(value * 100 + 1e-6) / 100


def is_holiday(day: date, cfg: dict) -> bool:
    return day.isoformat() in cfg.get("holidays", [])


def day_rate(day: date, cfg: dict) -> float:
    """Hourly rate for `day`, with the public holiday multiplier applied."""
    mult = cfg.get("holiday_multiplier", 2.5) if is_holiday(day, cfg) else 1.0
    return cfg["rate"] * mult


def day_pay(cfg: dict, day: date | None = None) -> float:
    """A full shift's pay (on `day`, if given, so holidays count)."""
    rate = day_rate(day, cfg) if day is not None else cfg["rate"]
    return rate * paid_hours(cfg)


def day_earnings(day: date, now: datetime, cfg: dict) -> float:
    """What `day` has earned as of `now`."""
    if not is_counted(day, cfg):
        return 0.0
    today = now.date()
    if day < today:
        return day_pay(cfg, day)
    if day > today:
        return 0.0
    return floor_cents(day_rate(day, cfg) * paid_seconds(now, cfg) / 3600)


def period_start(day: date, cfg: dict) -> date:
    """The payday (Wednesday) that opened the pay period containing `day`."""
    anchor = date.fromisoformat(cfg["payday"])
    return day - timedelta(days=(day - anchor).days % PERIOD_DAYS)


def period_days(start: date) -> list[date]:
    return [start + timedelta(days=i) for i in range(PERIOD_DAYS)]


def period_earnings(now: datetime, cfg: dict) -> float:
    """Earned so far this pay period, including today's running amount."""
    today = now.date()
    start = period_start(today, cfg)
    return floor_cents(
        sum(day_earnings(d, now, cfg) for d in period_days(start) if d <= today)
    )
