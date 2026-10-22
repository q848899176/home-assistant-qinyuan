"""Config flow for Qinyuan Smart Water Purifier."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    QinyuanAccountLockedError,
    QinyuanApiClient,
    QinyuanApiError,
    QinyuanAuthError,
    hash_password,
)
from .const import CONF_PASSWORD_HASH, CONF_PHONE, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN


def _schema(phone: str | None = None) -> vol.Schema:
    fields = {
        vol.Required(CONF_PHONE, **({"default": phone} if phone is not None else {})): vol.All(
            str, vol.Strip, vol.Length(min=1)
        ),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
    if phone is None:
        fields[vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL)] = vol.All(
            vol.Coerce(int), vol.Range(min=60)
        )
    return vol.Schema(fields)


async def _validation_error(hass: HomeAssistant, user_input: dict[str, Any]) -> str | None:
    """Validate credentials by logging in and reading the device list."""
    if not user_input[CONF_PASSWORD]:
        return "invalid_auth"
    api = QinyuanApiClient(
        async_get_clientsession(hass),
        user_input[CONF_PHONE],
        hash_password(user_input[CONF_PASSWORD]),
    )
    try:
        await api.async_login()
        await api.async_get_devices()
    except QinyuanAccountLockedError:
        return "account_locked"
    except QinyuanAuthError:
        return "invalid_auth"
    except QinyuanApiError:
        return "cannot_connect"
    return None


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
            if error := await _validation_error(self.hass, user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Qinyuan",
                    data={
                        CONF_PHONE: user_input[CONF_PHONE],
                        CONF_PASSWORD_HASH: hash_password(user_input[CONF_PASSWORD]),
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(),
            errors=errors,
        )

    async def async_step_import(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Import legacy YAML once; never overwrite credentials saved through the UI."""
        await self.async_set_unique_id(user_input[CONF_PHONE])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Qinyuan", data=user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self._async_credentials(
            self._get_reconfigure_entry(), "reconfigure", user_input
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self._async_credentials(self._get_reauth_entry(), "reauth_confirm", user_input)

    async def _async_credentials(
        self, entry: config_entries.ConfigEntry, step_id: str, user_input: dict[str, Any] | None
    ) -> config_entries.ConfigFlowResult:
        errors = {}
        if user_input is not None:
            if user_input[CONF_PHONE] != entry.data[CONF_PHONE]:
                errors[CONF_PHONE] = "wrong_account"
            elif error := await _validation_error(self.hass, user_input):
                errors["base"] = error
            else:
                await self.async_set_unique_id(user_input[CONF_PHONE])
                self._abort_if_unique_id_mismatch()
                data = {key: value for key, value in entry.data.items() if key != CONF_PASSWORD}
                data[CONF_PASSWORD_HASH] = hash_password(user_input[CONF_PASSWORD])
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id=step_id, data_schema=_schema(entry.data[CONF_PHONE]), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> QinyuanOptionsFlow:
        """Create the options flow."""
        return QinyuanOptionsFlow()


class QinyuanOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options for Qinyuan."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
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
