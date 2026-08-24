"""Tests for Hildebrand Glow external statistics construction."""
from datetime import date, datetime, timedelta, timezone

from homeassistant.components.recorder.models import StatisticData

from custom_components.hildebrand_glow.statistics import GlowmarktStatisticsImporter


def test_statistic_id_has_valid_object_prefix() -> None:
    importer = object.__new__(GlowmarktStatisticsImporter)
    importer.entry_id = "01K3-ABC.XYZ"

    assert (
        importer.statistic_id("electricity")
        == "hildebrand_glow:entry_01k3_abc_xyz_electricity_consumption"
    )


def _half_hours(start: datetime, count: int, value: float = 0.1):
    return [(start + timedelta(minutes=30 * index), value) for index in range(count)]


def test_build_statistics_preserves_zero_use_day() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    stats, running, complete, _started = GlowmarktStatisticsImporter._build_statistics(
        _half_hours(start, 48, 0.0),
        date(2026, 8, 1),
        date(2026, 8, 2),
        12.5,
    )

    assert len(stats) == 24
    assert running == 12.5
    assert complete == date(2026, 8, 2)
    assert all(stat["state"] == 0 for stat in stats)


def test_build_statistics_stops_before_incomplete_day() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    stats, running, complete, _started = GlowmarktStatisticsImporter._build_statistics(
        _half_hours(start, 47),
        date(2026, 8, 1),
        date(2026, 8, 2),
        0.0,
    )

    assert stats == []
    assert running == 0.0
    assert complete == date(2026, 8, 1)


def test_build_statistics_handles_short_dst_day() -> None:
    # Europe/London 2026-03-29 is 23 hours: 00:00 UTC to 23:00 UTC.
    start = datetime(2026, 3, 29, tzinfo=timezone.utc)
    stats, running, complete, _started = GlowmarktStatisticsImporter._build_statistics(
        _half_hours(start, 46),
        date(2026, 3, 29),
        date(2026, 3, 30),
        0.0,
    )

    assert len(stats) == 23
    assert running == 4.6
    assert complete == date(2026, 3, 30)


def test_build_statistics_handles_long_dst_day() -> None:
    # Europe/London 2026-10-25 is 25 hours: 23:00 UTC to 00:00 UTC.
    start = datetime(2026, 10, 24, 23, tzinfo=timezone.utc)
    stats, running, complete, _started = GlowmarktStatisticsImporter._build_statistics(
        _half_hours(start, 50),
        date(2026, 10, 25),
        date(2026, 10, 26),
        0.0,
    )

    assert len(stats) == 25
    assert running == 5.0
    assert complete == date(2026, 10, 26)


def test_cost_statistics_include_one_daily_standing_charge() -> None:
    importer = object.__new__(GlowmarktStatisticsImporter)
    importer.tariff_config = {
        "electricity_rate": 0.1978,
        "electricity_standing_charge": 0.5104,
        "electricity_tariff_effective_date": "2026-04-04",
        "tariff_history": [],
    }
    # A complete 1 August UK-local day starts at 23:00 UTC in summer.
    start = datetime(2026, 7, 31, 23, tzinfo=timezone.utc)
    consumption = [
        StatisticData(
            start=start + timedelta(hours=hour),
            state=0.1,
            sum=round((hour + 1) * 0.1, 6),
        )
        for hour in range(24)
    ]

    stats, running = importer._build_cost_statistics(
        consumption, 10.0, "electricity"
    )

    assert len(stats) == 24
    assert stats[0]["state"] == 0.53018
    assert all(stat["state"] == 0.01978 for stat in stats[1:])
    assert running == 10.98512
