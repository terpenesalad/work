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


def paid_seconds(now: datetime, cfg: dict) -> float:
    """Paid seconds worked so far today, pausing for the unpaid break."""
    total = cfg["hours"] * 3600
    start = datetime.combine(now.date(), _parse_hhmm(cfg["start"]))
    elapsed = (now - start).total_seconds()
    if elapsed <= 0:
        return 0.0

    break_len = cfg.get("break_minutes", 0) * 60
    if break_len > 0:
        b_start = datetime.combine(now.date(), _parse_hhmm(cfg["break_start"]))
        offset = (b_start - start).total_seconds()  # paid time before the break
        if 0 < offset < total and elapsed > offset:
            elapsed -= min(elapsed - offset, break_len)

    return min(elapsed, total)


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
    return rate * cfg["hours"]


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


def shift_end(day: date, cfg: dict) -> datetime:
    start = datetime.combine(day, _parse_hhmm(cfg["start"]))
    end = start + timedelta(hours=cfg["hours"])
    break_len = cfg.get("break_minutes", 0)
    if break_len > 0:
        b_start = datetime.combine(day, _parse_hhmm(cfg["break_start"]))
        if start < b_start < end:
            end += timedelta(minutes=break_len)
    return end
