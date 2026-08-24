"""Import delayed Glowmarkt consumption into Home Assistant statistics."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_conversion import EnergyConverter

from .api import GlowmarktApiClient, GlowmarktApiError, GlowmarktAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UK_TZ = ZoneInfo("Europe/London")
INITIAL_HISTORY_DAYS = 90
RECONCILE_DAYS = 7
CHUNK_DAYS = 7
FINALIZATION_DELAY_DAYS = 2

CONSUMPTION_CLASSIFIERS = {
    "electricity.consumption": "electricity",
    "gas.consumption": "gas",
}


class GlowmarktStatisticsImporter:
    """Synchronize delayed Glowmarkt readings to owned external statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: GlowmarktApiClient,
        entry_id: str,
        tariff_config: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.api_client = api_client
        self.entry_id = entry_id
        self.tariff_config = tariff_config
        self._lock = asyncio.Lock()
        self.last_success: datetime | None = None
        self.last_error: str | None = None

    def statistic_id(self, fuel: str) -> str:
        """Return a stable statistic ID for one fuel."""
        safe_entry_id = re.sub(r"[^a-z0-9]+", "_", self.entry_id.lower()).strip("_")
        return f"{DOMAIN}:entry_{safe_entry_id}_{fuel}_consumption"

    def cost_statistic_id(self, fuel: str) -> str:
        """Return the paired cumulative-cost statistic ID."""
        safe_entry_id = re.sub(r"[^a-z0-9]+", "_", self.entry_id.lower()).strip("_")
        return f"{DOMAIN}:entry_{safe_entry_id}_{fuel}_cost"

    def update_tariff_config(self, tariff_config: dict[str, Any]) -> None:
        """Use updated tariff periods on the next synchronization."""
        self.tariff_config = tariff_config

    async def async_sync(self, resources: dict[str, dict[str, Any]]) -> None:
        """Import all available finalized consumption data."""
        if self._lock.locked():
            return

        async with self._lock:
            try:
                for classifier, fuel in CONSUMPTION_CLASSIFIERS.items():
                    resource = resources.get(classifier)
                    if resource is None:
                        continue
                    await self._async_sync_resource(
                        fuel,
                        resource["resource_id"],
                    )
            except (GlowmarktApiError, GlowmarktAuthError, HomeAssistantError) as err:
                self.last_error = str(err)
                _LOGGER.warning("Historical statistics sync paused: %s", err)
                return

            self.last_success = datetime.now(timezone.utc)
            self.last_error = None

    async def _async_get_recent_statistics(
        self, statistic_id: str
    ) -> list[dict[str, Any]]:
        """Return enough recent rows to establish an overlap baseline."""
        # The reconciliation start is derived from the latest row's local date
        # and therefore spans parts of eight dates. Keep two additional days so
        # an existing broken boundary can still be reached and repaired.
        row_limit = (RECONCILE_DAYS + 2) * 25 + 1
        result = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics,
            self.hass,
            row_limit,
            statistic_id,
            False,
            {"sum"},
        )
        return result.get(statistic_id, [])

    async def _async_sync_resource(self, fuel: str, resource_id: str) -> None:
        statistic_id = self.statistic_id(fuel)
        recent = await self._async_get_recent_statistics(statistic_id)
        cost_statistic_id = self.cost_statistic_id(fuel)
        recent_cost = await self._async_get_recent_statistics(cost_statistic_id)

        today_uk = datetime.now(UK_TZ).date()
        cutoff_day = today_uk - timedelta(days=FINALIZATION_DELAY_DAYS)
        end_uk = datetime.combine(cutoff_day, time.min, UK_TZ)

        if recent and (recent_cost or not self._tariff_periods(fuel)):
            # Recorder does not guarantee that these rows are returned newest
            # first. Select by timestamp explicitly; using recent[0] can move
            # the reconciliation window backwards and reset its cumulative sum.
            latest_start = datetime.fromtimestamp(
                max(row["start"] for row in recent), timezone.utc
            )
            start_uk = datetime.combine(
                (latest_start.astimezone(UK_TZ).date() - timedelta(days=RECONCILE_DAYS)),
                time.min,
                UK_TZ,
            )
        else:
            start_uk = datetime.combine(
                today_uk - timedelta(days=INITIAL_HISTORY_DAYS),
                time.min,
                UK_TZ,
            )

        if start_uk >= end_uk:
            return

        baseline = 0.0
        start_timestamp = start_uk.astimezone(timezone.utc).timestamp()
        preceding_rows = [row for row in recent if row["start"] < start_timestamp]
        if preceding_rows:
            preceding = max(preceding_rows, key=lambda row: row["start"])
            baseline = float(preceding.get("sum") or 0.0)

        cost_baseline = 0.0
        preceding_cost_rows = [
            row for row in recent_cost if row["start"] < start_timestamp
        ]
        if preceding_cost_rows:
            preceding_cost = max(preceding_cost_rows, key=lambda row: row["start"])
            cost_baseline = float(preceding_cost.get("sum") or 0.0)

        cursor = start_uk
        running_sum = baseline
        cost_running_sum = cost_baseline
        import_started = bool(recent)
        while cursor < end_uk:
            chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end_uk)
            readings = await self.api_client.get_interval_readings(
                resource_id,
                cursor.astimezone(timezone.utc),
                chunk_end.astimezone(timezone.utc),
            )
            statistics, running_sum, complete_through, import_started = self._build_statistics(
                readings,
                cursor.date(),
                chunk_end.date(),
                running_sum,
                import_started,
            )
            if statistics:
                async_add_external_statistics(
                    self.hass,
                    self._metadata(statistic_id, fuel),
                    statistics,
                )
                _LOGGER.info(
                    "Imported %d hourly %s statistics through %s",
                    len(statistics),
                    fuel,
                    complete_through,
                )
                cost_statistics, cost_running_sum = self._build_cost_statistics(
                    statistics, cost_running_sum, fuel
                )
                if cost_statistics:
                    async_add_external_statistics(
                        self.hass,
                        self._cost_metadata(cost_statistic_id, fuel),
                        cost_statistics,
                    )
                    _LOGGER.info(
                        "Imported %d hourly %s cost statistics through %s",
                        len(cost_statistics),
                        fuel,
                        complete_through,
                    )

            if complete_through < chunk_end.date():
                _LOGGER.info(
                    "Stopping %s import at incomplete Glowmarkt day %s",
                    fuel,
                    complete_through,
                )
                return
            cursor = chunk_end

    @staticmethod
    def _metadata(statistic_id: str, fuel: str) -> StatisticMetaData:
        return StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"Hildebrand Glow {fuel.title()} Consumption",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

    @staticmethod
    def _cost_metadata(statistic_id: str, fuel: str) -> StatisticMetaData:
        """Return metadata for an Energy Dashboard-compatible cost statistic."""
        return StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"Hildebrand Glow {fuel.title()} Cost",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=None,
            unit_of_measurement=None,
        )

    def _tariff_periods(self, fuel: str) -> list[tuple[date, float, float]]:
        """Return all known tariff periods for a fuel, sorted by start date."""
        periods: list[tuple[date, float, float]] = []
        for item in self.tariff_config.get("tariff_history", []):
            if item.get("fuel") == fuel:
                periods.append(
                    (
                        date.fromisoformat(item["effective_from"]),
                        float(item["unit_rate"]),
                        float(item["standing_charge"]),
                    )
                )
        effective = self.tariff_config.get(f"{fuel}_tariff_effective_date")
        if effective:
            periods.append(
                (
                    date.fromisoformat(effective),
                    float(self.tariff_config[f"{fuel}_rate"]),
                    float(self.tariff_config[f"{fuel}_standing_charge"]),
                )
            )
        return sorted(set(periods), key=lambda period: period[0])

    def _build_cost_statistics(
        self,
        consumption: list[StatisticData],
        baseline: float,
        fuel: str,
    ) -> tuple[list[StatisticData], float]:
        """Calculate hourly cumulative cost, charging standing once per local day."""
        periods = self._tariff_periods(fuel)
        if not periods:
            return [], baseline

        result: list[StatisticData] = []
        running_sum = baseline
        charged_day: date | None = None
        for statistic in consumption:
            start = statistic["start"]
            local_day = start.astimezone(UK_TZ).date()
            applicable = [period for period in periods if period[0] <= local_day]
            if not applicable:
                continue
            _, unit_rate, standing_charge = applicable[-1]
            state = float(statistic["state"] or 0.0) * unit_rate
            if local_day != charged_day:
                state += standing_charge
                charged_day = local_day
            state = round(state, 6)
            running_sum = round(running_sum + state, 6)
            result.append(StatisticData(start=start, state=state, sum=running_sum))
        return result, running_sum

    @staticmethod
    def _build_statistics(
        readings: list[tuple[datetime, float]],
        start_day: date,
        end_day: date,
        baseline: float,
        import_started: bool = True,
    ) -> tuple[list[StatisticData], float, date, bool]:
        """Build contiguous complete local-day hourly statistics.

        A complete UK-local day contains one reading for every 30-minute UTC
        slot. This naturally handles 23-hour and 25-hour DST days.
        """
        by_day: dict[date, dict[datetime, float]] = defaultdict(dict)
        for timestamp, value in readings:
            by_day[timestamp.astimezone(UK_TZ).date()][timestamp] = value

        result: list[StatisticData] = []
        running_sum = baseline
        day = start_day
        while day < end_day:
            day_start = datetime.combine(day, time.min, UK_TZ).astimezone(timezone.utc)
            next_start = datetime.combine(
                day + timedelta(days=1), time.min, UK_TZ
            ).astimezone(timezone.utc)
            expected_slots = int((next_start - day_start).total_seconds() // 1800)
            values = by_day.get(day, {})
            expected_timestamps = {
                day_start + timedelta(minutes=30 * index)
                for index in range(expected_slots)
            }
            if set(values) != expected_timestamps:
                if not import_started:
                    # Accounts can begin part-way through the initial day.
                    # Skip only leading incomplete days; gaps after the first
                    # complete day stop the import so later sums cannot mask
                    # missing consumption.
                    day += timedelta(days=1)
                    continue
                return result, running_sum, day, import_started

            import_started = True
            hourly: dict[datetime, float] = defaultdict(float)
            for timestamp in sorted(values):
                hour = timestamp.replace(minute=0, second=0, microsecond=0)
                hourly[hour] += values[timestamp]
            for hour in sorted(hourly):
                state = round(hourly[hour], 6)
                running_sum = round(running_sum + state, 6)
                result.append(
                    StatisticData(start=hour, state=state, sum=running_sum)
                )
            day += timedelta(days=1)

        return result, running_sum, end_day, import_started
