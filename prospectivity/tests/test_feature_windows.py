"""Window definitions for the feature stack (offline; dates only)."""

from datetime import datetime, timezone

from prospectivity.gee_features import baseline_windows, current_window, dry_season_window

REF = datetime(2026, 9, 23, tzinfo=timezone.utc)


def test_current_window_is_last_90_days():
    start, end = current_window(REF)
    assert end == REF and (end - start).days == 90


def test_baseline_uses_same_days_of_year_in_each_prior_year():
    cur_s, cur_e = current_window(REF)
    wins = baseline_windows(REF)
    assert [s.year for s, _ in wins] == [2025, 2024, 2023]
    for s, e in wins:
        assert (s.month, s.day) == (cur_s.month, cur_s.day)
        assert (e.month, e.day) == (cur_e.month, cur_e.day)


def test_baseline_leap_day_falls_back_to_28_feb():
    ref = datetime(2028, 2, 29, tzinfo=timezone.utc)
    (s, e), = baseline_windows(ref, years=1)
    assert (e.year, e.month, e.day) == (2027, 2, 28)


def test_dry_season_is_most_recent_completed_feb_to_may():
    s, e = dry_season_window(REF)
    assert (s.year, s.month, s.day) == (2026, 2, 1) and (e.month, e.day) == (6, 1)
    # Before the dry season has finished, use the previous year's.
    s, e = dry_season_window(datetime(2026, 4, 10, tzinfo=timezone.utc))
    assert s.year == 2025 and e.year == 2025
