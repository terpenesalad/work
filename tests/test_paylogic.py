import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import paylogic as p  # noqa: E402


def cfg(**kw):
    base = {
        "rate": 34.0,
        "start": "09:00",
        "end": "16:30",
        "break_start": "12:00",
        "break_minutes": 0,
        "workdays": [0, 1, 2, 3, 4],
        "payday": "2026-11-25",  # a Wednesday
        "overrides": {},
    }
    base.update(kw)
    return base


class DayTests(unittest.TestCase):
    def test_full_shift_is_255(self):
        self.assertEqual(p.day_pay(cfg()), 255.0)

    def test_before_shift_zero(self):
        self.assertEqual(p.day_earnings(date(2026, 11, 25), datetime(2026, 11, 25, 8, 59), cfg()), 0)

    def test_mid_shift(self):
        # 1 hour in = $34
        self.assertEqual(p.day_earnings(date(2026, 11, 25), datetime(2026, 11, 25, 10, 0), cfg()), 34.0)

    def test_after_shift_capped(self):
        self.assertEqual(p.day_earnings(date(2026, 11, 25), datetime(2026, 11, 25, 22, 0), cfg()), 255.0)

    def test_weekend_zero(self):
        sat = date(2026, 11, 28)
        self.assertEqual(p.day_earnings(sat, datetime(2026, 11, 28, 15, 0), cfg()), 0)

    def test_void_today(self):
        c = cfg(overrides={"2026-11-25": False})
        self.assertEqual(p.day_earnings(date(2026, 11, 25), datetime(2026, 11, 25, 15, 0), c), 0)

    def test_extra_day(self):
        c = cfg(overrides={"2026-11-28": True})
        self.assertEqual(p.day_earnings(date(2026, 11, 28), datetime(2026, 11, 28, 22, 0), c), 255.0)

    def test_break_pauses_counter(self):
        c = cfg(start="08:30", end="16:30", break_minutes=30, break_start="12:00")
        d = date(2026, 11, 25)
        at_break = p.day_earnings(d, datetime(2026, 11, 25, 12, 0), c)
        self.assertEqual(at_break, 119.0)  # 3.5h
        self.assertEqual(p.day_earnings(d, datetime(2026, 11, 25, 12, 29), c), at_break)
        self.assertEqual(p.day_earnings(d, datetime(2026, 11, 25, 13, 30), c), 153.0)  # 4.5h
        self.assertEqual(p.day_earnings(d, datetime(2026, 11, 25, 16, 29), c), p.floor_cents(255.0 - 34 / 60))
        self.assertEqual(p.day_earnings(d, datetime(2026, 11, 25, 16, 30), c), 255.0)
        self.assertEqual(p.paid_hours(c), 7.5)

    def test_stops_at_finish_time(self):
        # 9 to 5 with a 30 min lunch = 7.5 paid hours; nothing after 5pm
        c = cfg(start="09:00", end="17:00", break_minutes=30, break_start="12:30")
        d = date(2026, 11, 25)
        self.assertEqual(p.paid_hours(c), 7.5)
        self.assertEqual(p.day_earnings(d, datetime(2026, 11, 25, 17, 0), c), 255.0)
        self.assertEqual(p.day_earnings(d, datetime(2026, 11, 25, 17, 3, 30), c), 255.0)
        self.assertEqual(p.day_earnings(d, datetime(2026, 11, 25, 23, 59), c), 255.0)

    def test_paid_hours_from_times(self):
        self.assertEqual(p.paid_hours(cfg()), 7.5)
        self.assertEqual(p.paid_hours(cfg(end="17:00", break_minutes=30)), 7.5)
        # break outside the shift doesn't count
        self.assertEqual(p.paid_hours(cfg(break_minutes=30, break_start="18:00")), 7.5)


class HolidayTests(unittest.TestCase):
    def test_full_holiday_shift(self):
        c = cfg(holidays=["2026-11-25"])
        self.assertEqual(p.day_earnings(date(2026, 11, 25), datetime(2026, 11, 25, 22, 0), c), 637.5)

    def test_holiday_runs_faster(self):
        c = cfg(holidays=["2026-11-25"])
        self.assertEqual(p.day_earnings(date(2026, 11, 25), datetime(2026, 11, 25, 10, 0), c), 85.0)

    def test_custom_multiplier(self):
        c = cfg(holidays=["2026-11-25"], holiday_multiplier=2.25)
        self.assertEqual(p.day_pay(c, date(2026, 11, 25)), 573.75)

    def test_voided_holiday_is_zero(self):
        c = cfg(holidays=["2026-11-25"], overrides={"2026-11-25": False})
        self.assertEqual(p.day_earnings(date(2026, 11, 25), datetime(2026, 11, 25, 22, 0), c), 0)

    def test_holiday_in_period(self):
        c = cfg(holidays=["2026-11-26"])
        self.assertEqual(p.period_earnings(datetime(2026, 12, 8, 23, 0), c), 2550.0 - 255 + 637.5)


class PeriodTests(unittest.TestCase):
    def test_period_start_on_payday(self):
        self.assertEqual(p.period_start(date(2026, 11, 25), cfg()), date(2026, 11, 25))

    def test_period_start_mid_period(self):
        self.assertEqual(p.period_start(date(2026, 12, 8), cfg()), date(2026, 11, 25))
        self.assertEqual(p.period_start(date(2026, 12, 9), cfg()), date(2026, 12, 9))

    def test_period_before_anchor(self):
        self.assertEqual(p.period_start(date(2026, 11, 24), cfg()), date(2026, 11, 11))

    def test_resets_on_payday(self):
        # Tue 8 Dec, end of day: Wed25..Fri27 + Mon30..Fri4 + Mon7,Tue8 = 10 shifts
        self.assertEqual(p.period_earnings(datetime(2026, 12, 8, 23, 0), cfg()), 2550.0)
        # Payday Wed 9 Dec before shift: reset to zero
        self.assertEqual(p.period_earnings(datetime(2026, 12, 9, 8, 0), cfg()), 0.0)

    def test_period_includes_today_running(self):
        # Thu 26 Nov 10am: Wed full + 1h
        self.assertEqual(p.period_earnings(datetime(2026, 11, 26, 10, 0), cfg()), 289.0)

    def test_void_in_period(self):
        c = cfg(overrides={"2026-11-30": False})
        self.assertEqual(p.period_earnings(datetime(2026, 12, 8, 23, 0), c), 2295.0)


if __name__ == "__main__":
    unittest.main()
