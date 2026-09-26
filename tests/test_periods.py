from datetime import datetime, timedelta, timezone

from app.periods import period_window


def test_daily_window_resets_at_berlin_midnight():
    window = period_window("daily", datetime(2026, 9, 26, 12, tzinfo=timezone.utc))

    assert window.start_utc == datetime(2026, 9, 25, 22, tzinfo=timezone.utc)
    assert window.end_utc == datetime(2026, 9, 26, 22, tzinfo=timezone.utc)
    assert window.reset_at_utc == window.end_utc


def test_weekly_window_starts_monday_in_berlin():
    window = period_window("weekly", datetime(2026, 9, 26, 12, tzinfo=timezone.utc))

    assert window.start_utc == datetime(2026, 9, 20, 22, tzinfo=timezone.utc)
    assert window.end_utc == datetime(2026, 9, 27, 22, tzinfo=timezone.utc)
    assert window.reset_at_utc == window.end_utc


def test_monthly_window_handles_month_end():
    window = period_window("monthly", datetime(2026, 2, 28, 12, tzinfo=timezone.utc))

    assert window.start_utc == datetime(2026, 1, 31, 23, tzinfo=timezone.utc)
    assert window.end_utc == datetime(2026, 2, 28, 23, tzinfo=timezone.utc)
    assert window.reset_at_utc == window.end_utc


def test_dst_short_day_has_correct_utc_duration():
    window = period_window("daily", datetime(2026, 3, 29, 12, tzinfo=timezone.utc))

    assert window.start_utc == datetime(2026, 3, 28, 23, tzinfo=timezone.utc)
    assert window.end_utc == datetime(2026, 3, 29, 22, tzinfo=timezone.utc)
    assert window.end_utc - window.start_utc == timedelta(hours=23)


def test_lifetime_window_has_no_reset():
    window = period_window("lifetime", datetime(2026, 9, 26, 12, tzinfo=timezone.utc))

    assert window.start_utc.tzinfo is timezone.utc
    assert window.end_utc is None
    assert window.reset_at_utc is None
