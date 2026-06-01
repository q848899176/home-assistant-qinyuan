"""Config flow for Qinyuan Smart Water Purifier."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import QinyuanApiClient, QinyuanApiError, normalize_password_hash
from .const import CONF_PASSWORD_HASH, CONF_PHONE, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN


def _schema(default_scan_interval: int = DEFAULT_SCAN_INTERVAL) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PHONE): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=default_scan_interval): vol.All(
                vol.Coerce(int), vol.Range(min=60)
            ),
        }
    )


async def _validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Validate credentials by logging in and reading the device list."""
    api = QinyuanApiClient(
        async_get_clientsession(hass),
        user_input[CONF_PHONE],
        normalize_password_hash(user_input[CONF_PASSWORD]),
    )
    await api.async_login()
    await api.async_get_devices()


class QinyuanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qinyuan."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_PHONE])
            self._abort_if_unique_id_configured()
            try:
                await _validate_input(self.hass, user_input)
            except QinyuanApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Qinyuan",
                    data={
                        CONF_PHONE: user_input[CONF_PHONE],
                        CONF_PASSWORD_HASH: normalize_password_hash(user_input[CONF_PASSWORD]),
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> QinyuanOptionsFlow:
        """Create the options flow."""
        return QinyuanOptionsFlow(config_entry)


class QinyuanOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Qinyuan."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=60)
                    )
                }
            ),
        )
