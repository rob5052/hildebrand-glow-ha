"""Sensor platform for Hildebrand Glow integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, CLASSIFIER_ELECTRICITY_CONSUMPTION, CLASSIFIER_ELECTRICITY_COST, CLASSIFIER_GAS_CONSUMPTION, CLASSIFIER_GAS_COST
from .coordinator import GlowmarktDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: dict[str, dict[str, Any]] = {
    CLASSIFIER_ELECTRICITY_CONSUMPTION: {"name": "Electricity Consumption", "icon": "mdi:flash", "device_class": SensorDeviceClass.ENERGY, "state_class": SensorStateClass.TOTAL_INCREASING, "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "data_key": "readings", "reading_key": CLASSIFIER_ELECTRICITY_CONSUMPTION},
    CLASSIFIER_GAS_CONSUMPTION: {"name": "Gas Consumption", "icon": "mdi:fire", "device_class": SensorDeviceClass.ENERGY, "state_class": SensorStateClass.TOTAL_INCREASING, "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR, "data_key": "readings", "reading_key": CLASSIFIER_GAS_CONSUMPTION},
    f"{CLASSIFIER_ELECTRICITY_COST}_api": {"name": "Electricity Cost (API)", "icon": "mdi:currency-gbp", "device_class": SensorDeviceClass.MONETARY, "state_class": SensorStateClass.TOTAL, "native_unit_of_measurement": "GBP", "data_key": "readings", "reading_key": CLASSIFIER_ELECTRICITY_COST, "convert_pence": True, "resets_daily": True},
    f"{CLASSIFIER_GAS_COST}_api": {"name": "Gas Cost (API)", "icon": "mdi:currency-gbp", "device_class": SensorDeviceClass.MONETARY, "state_class": SensorStateClass.TOTAL, "native_unit_of_measurement": "GBP", "data_key": "readings", "reading_key": CLASSIFIER_GAS_COST, "convert_pence": True, "resets_daily": True},
    "electricity_daily_cost": {"name": "Electricity Daily Cost", "icon": "mdi:currency-gbp", "device_class": SensorDeviceClass.MONETARY, "state_class": SensorStateClass.TOTAL, "native_unit_of_measurement": "GBP", "data_key": "costs", "reading_key": "electricity", "resets_daily": True},
    "gas_daily_cost": {"name": "Gas Daily Cost", "icon": "mdi:currency-gbp", "device_class": SensorDeviceClass.MONETARY, "state_class": SensorStateClass.TOTAL, "native_unit_of_measurement": "GBP", "data_key": "costs", "reading_key": "gas", "resets_daily": True},
    "total_daily_cost": {"name": "Total Daily Energy Cost", "icon": "mdi:currency-gbp", "device_class": SensorDeviceClass.MONETARY, "state_class": SensorStateClass.TOTAL, "native_unit_of_measurement": "GBP", "data_key": "costs", "reading_key": "total", "resets_daily": True},
    "daily_standing_charges": {"name": "Daily Standing Charges", "icon": "mdi:cash-clock", "device_class": SensorDeviceClass.MONETARY, "state_class": SensorStateClass.TOTAL, "native_unit_of_measurement": "GBP", "data_key": "costs", "reading_key": "standing_charges_total", "resets_daily": True},
    "electricity_unit_rate": {"name": "Electricity Unit Rate", "icon": "mdi:currency-gbp", "state_class": SensorStateClass.MEASUREMENT, "native_unit_of_measurement": "GBP/kWh", "suggested_display_precision": 5, "data_key": "tariffs", "reading_key": "electricity_rate", "rate_precision": 5},
    "gas_unit_rate": {"name": "Gas Unit Rate", "icon": "mdi:currency-gbp", "state_class": SensorStateClass.MEASUREMENT, "native_unit_of_measurement": "GBP/kWh", "suggested_display_precision": 5, "data_key": "tariffs", "reading_key": "gas_rate", "rate_precision": 5},
    "electricity_standing_charge": {"name": "Electricity Standing Charge", "icon": "mdi:cash-clock", "state_class": SensorStateClass.MEASUREMENT, "native_unit_of_measurement": "GBP/day", "suggested_display_precision": 5, "data_key": "tariffs", "reading_key": "electricity_standing_charge", "rate_precision": 5},
    "gas_standing_charge": {"name": "Gas Standing Charge", "icon": "mdi:cash-clock", "state_class": SensorStateClass.MEASUREMENT, "native_unit_of_measurement": "GBP/day", "suggested_display_precision": 5, "data_key": "tariffs", "reading_key": "gas_standing_charge", "rate_precision": 5},
}

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GlowmarktDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[GlowmarktSensor] = []
    await coordinator.async_config_entry_first_refresh()
    for sensor_key, description in SENSOR_DESCRIPTIONS.items():
        entities.append(GlowmarktSensor(coordinator=coordinator, sensor_key=sensor_key, description=description, entry_id=config_entry.entry_id))
    async_add_entities(entities)

class GlowmarktSensor(CoordinatorEntity[GlowmarktDataUpdateCoordinator], SensorEntity):
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: GlowmarktDataUpdateCoordinator, sensor_key: str, description: dict[str, Any], entry_id: str) -> None:
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._description = description
        self._attr_unique_id = f"{entry_id}_{sensor_key}"
        self._attr_name = description["name"]
        self._attr_icon = description.get("icon")
        self._attr_device_class = description.get("device_class")
        self._attr_state_class = description.get("state_class")
        self._attr_native_unit_of_measurement = description.get("native_unit_of_measurement")
        self._attr_suggested_display_precision = description.get("suggested_display_precision")
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)}, name="Smart Meter", manufacturer="Hildebrand Technology", model="SMETS2 via Glow/Bright", configuration_url="https://glowmarkt.com/")

    @property
    def last_reset(self) -> datetime | None:
        """Return the start of the current local day for daily-resetting totals."""
        if self._description.get("resets_daily", False):
            return dt_util.start_of_local_day()
        return None

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        data_key = self._description.get("data_key", "readings")
        reading_key = self._description.get("reading_key", "")
        data_section = self.coordinator.data.get(data_key, {})
        value = data_section.get(reading_key)
        if value is None:
            return None
        if self._description.get("convert_pence", False):
            value = round(value / 100.0, 2)
        if isinstance(value, float):
            if rate_precision := self._description.get("rate_precision"):
                return round(value, rate_precision)
            return round(value, 3) if self._attr_device_class != SensorDeviceClass.MONETARY else round(value, 2)
        return value
