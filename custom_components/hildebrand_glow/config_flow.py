"""Config flow for Hildebrand Glow integration."""
from __future__ import annotations

from datetime import date
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GlowmarktApiClient, GlowmarktApiError, GlowmarktAuthError
from .const import (
    CONF_ELECTRICITY_RATE,
    CONF_ELECTRICITY_STANDING_CHARGE,
    CONF_ELECTRICITY_TARIFF_EFFECTIVE_DATE,
    CONF_GAS_RATE,
    CONF_GAS_STANDING_CHARGE,
    CONF_GAS_TARIFF_EFFECTIVE_DATE,
    CONF_TARIFF_HISTORY,
    DEFAULT_ELECTRICITY_RATE,
    DEFAULT_ELECTRICITY_STANDING_CHARGE,
    DEFAULT_GAS_RATE,
    DEFAULT_GAS_STANDING_CHARGE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _iso_date(value: Any) -> str:
    """Validate and retain an ISO calendar date."""
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError as err:
        raise vol.Invalid("Date must use YYYY-MM-DD") from err
    return parsed.isoformat()


_ISO_DATE = vol.All(str, _iso_date)


def _tariff_schema(current: dict[str, Any]) -> vol.Schema:
    """Return the tariff form schema."""
    today = date.today().isoformat()
    return vol.Schema(
        {
            vol.Required(CONF_ELECTRICITY_RATE, default=current.get(CONF_ELECTRICITY_RATE, DEFAULT_ELECTRICITY_RATE)): vol.Coerce(float),
            vol.Required(CONF_ELECTRICITY_STANDING_CHARGE, default=current.get(CONF_ELECTRICITY_STANDING_CHARGE, DEFAULT_ELECTRICITY_STANDING_CHARGE)): vol.Coerce(float),
            vol.Required(CONF_ELECTRICITY_TARIFF_EFFECTIVE_DATE, default=current.get(CONF_ELECTRICITY_TARIFF_EFFECTIVE_DATE, today)): _ISO_DATE,
            vol.Required(CONF_GAS_RATE, default=current.get(CONF_GAS_RATE, DEFAULT_GAS_RATE)): vol.Coerce(float),
            vol.Required(CONF_GAS_STANDING_CHARGE, default=current.get(CONF_GAS_STANDING_CHARGE, DEFAULT_GAS_STANDING_CHARGE)): vol.Coerce(float),
            vol.Required(CONF_GAS_TARIFF_EFFECTIVE_DATE, default=current.get(CONF_GAS_TARIFF_EFFECTIVE_DATE, today)): _ISO_DATE,
        }
    )


def _updated_history(current: dict[str, Any], user_input: dict[str, Any]) -> list[dict[str, Any]]:
    """Retain the previous tariff when a new dated tariff is submitted."""
    history = list(current.get(CONF_TARIFF_HISTORY, []))
    for fuel in ("electricity", "gas"):
        rate_key = f"{fuel}_rate"
        standing_key = f"{fuel}_standing_charge"
        date_key = f"{fuel}_tariff_effective_date"
        old_date = current.get(date_key)
        changed = (
            float(current.get(rate_key, 0)) != float(user_input[rate_key])
            or float(current.get(standing_key, 0)) != float(user_input[standing_key])
        )
        if old_date and changed and user_input[date_key] > old_date:
            previous = {
                "fuel": fuel,
                "effective_from": old_date,
                "unit_rate": float(current[rate_key]),
                "standing_charge": float(current[standing_key]),
            }
            if previous not in history:
                history.append(previous)
    return sorted(history, key=lambda item: (item["fuel"], item["effective_from"]))


class HildebrandGlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hildebrand Glow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = GlowmarktApiClient(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                if await client.test_connection():
                    self._user_data = user_input
                    return await self.async_step_tariff()
                errors["base"] = "no_resources"
            except GlowmarktAuthError:
                errors["base"] = "invalid_auth"
            except GlowmarktApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_tariff(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            data = {**self._user_data, **user_input}
            await self.async_set_unique_id(self._user_data[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"Smart Meter ({self._user_data[CONF_USERNAME]})", data=data)
        return self.async_show_form(step_id="tariff", data_schema=_tariff_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> HildebrandGlowOptionsFlow:
        return HildebrandGlowOptionsFlow()


class HildebrandGlowOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Hildebrand Glow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        current = dict(self.config_entry.data)
        if user_input is not None:
            for fuel in ("electricity", "gas"):
                date_key = f"{fuel}_tariff_effective_date"
                rate_key = f"{fuel}_rate"
                standing_key = f"{fuel}_standing_charge"
                changed = (
                    float(current.get(rate_key, 0)) != float(user_input[rate_key])
                    or float(current.get(standing_key, 0)) != float(user_input[standing_key])
                )
                if changed and current.get(date_key) and user_input[date_key] < current[date_key]:
                    return self.async_show_form(
                        step_id="init",
                        data_schema=_tariff_schema(user_input),
                        errors={"base": "invalid_effective_date"},
                    )

            new_data = {**current, **user_input}
            new_data[CONF_TARIFF_HISTORY] = _updated_history(current, user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=_tariff_schema(current))
