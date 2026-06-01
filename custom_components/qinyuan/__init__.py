"""Qinyuan Smart Water Purifier integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import QinyuanApiClient, normalize_password_hash
from .const import CONF_PASSWORD_HASH, CONF_PHONE, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import QinyuanDataUpdateCoordinator

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Qinyuan from a config entry."""
    data = dict(entry.data)
    password_hash = data.get(CONF_PASSWORD_HASH)
    if not password_hash and data.get(CONF_PASSWORD):
        password_hash = normalize_password_hash(data[CONF_PASSWORD])
        hass.config_entries.async_update_entry(
            entry,
            data={key: value for key, value in data.items() if key != CONF_PASSWORD}
            | {CONF_PASSWORD_HASH: password_hash},
        )

    api = QinyuanApiClient(
        async_get_clientsession(hass),
        data[CONF_PHONE],
        password_hash,
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
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
