"""Qinyuan Smart Water Purifier integration."""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import QinyuanApiClient, hash_password
from .const import (
    CONF_PASSWORD_HASH,
    CONF_PHONE,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USER_AGENT,
    DOMAIN,
)
from .coordinator import QinyuanDataUpdateCoordinator

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Required(CONF_PHONE): cv.string,
                vol.Required(CONF_PASSWORD_HASH): cv.string,
                vol.Optional("user_agent", default=DEFAULT_USER_AGENT): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=60)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Support existing YAML installations without replacing UI credentials."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Qinyuan from a config entry."""
    data = dict(entry.data)
    password_hash = data.get(CONF_PASSWORD_HASH)
    if not password_hash and data.get(CONF_PASSWORD):
        password_hash = hash_password(data[CONF_PASSWORD])
        hass.config_entries.async_update_entry(
            entry,
            data={key: value for key, value in data.items() if key != CONF_PASSWORD}
            | {CONF_PASSWORD_HASH: password_hash},
        )

    api = QinyuanApiClient(
        async_get_clientsession(hass),
        data[CONF_PHONE],
        password_hash,
        user_agent=data.get("user_agent", DEFAULT_USER_AGENT),
    )
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    coordinator = QinyuanDataUpdateCoordinator(
        hass,
        entry,
        api,
        update_interval=timedelta(seconds=int(scan_interval)),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
