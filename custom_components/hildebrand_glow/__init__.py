"""The Hildebrand Glow integration."""
from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import GlowmarktApiClient
from .const import DOMAIN, CONF_ELECTRICITY_RATE, CONF_GAS_RATE, CONF_ELECTRICITY_STANDING_CHARGE, CONF_GAS_STANDING_CHARGE, CONF_ELECTRICITY_TARIFF_EFFECTIVE_DATE, CONF_GAS_TARIFF_EFFECTIVE_DATE, CONF_TARIFF_HISTORY, DEFAULT_ELECTRICITY_RATE, DEFAULT_GAS_RATE, DEFAULT_ELECTRICITY_STANDING_CHARGE, DEFAULT_GAS_STANDING_CHARGE
from .coordinator import GlowmarktDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    client = GlowmarktApiClient(username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD], session=session)
    tariff_config = _tariff_config(entry)
    coordinator = GlowmarktDataUpdateCoordinator(hass=hass, api_client=client, tariff_config=tariff_config, config_entry=entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.start_statistics_sync()
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: GlowmarktDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    tariff_config = _tariff_config(entry)
    coordinator.update_tariff_config(tariff_config)
    await coordinator.async_request_refresh()


def _tariff_config(entry: ConfigEntry) -> dict:
    """Build the coordinator tariff configuration from the config entry."""
    return {
        "electricity_rate": entry.data.get(CONF_ELECTRICITY_RATE, DEFAULT_ELECTRICITY_RATE),
        "gas_rate": entry.data.get(CONF_GAS_RATE, DEFAULT_GAS_RATE),
        "electricity_standing_charge": entry.data.get(CONF_ELECTRICITY_STANDING_CHARGE, DEFAULT_ELECTRICITY_STANDING_CHARGE),
        "gas_standing_charge": entry.data.get(CONF_GAS_STANDING_CHARGE, DEFAULT_GAS_STANDING_CHARGE),
        "electricity_tariff_effective_date": entry.data.get(CONF_ELECTRICITY_TARIFF_EFFECTIVE_DATE),
        "gas_tariff_effective_date": entry.data.get(CONF_GAS_TARIFF_EFFECTIVE_DATE),
        "tariff_history": list(entry.data.get(CONF_TARIFF_HISTORY, [])),
    }

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
