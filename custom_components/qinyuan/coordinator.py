"""Data coordinator for the Qinyuan integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import QinyuanApiClient, QinyuanAuthError, QinyuanApiError
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class QinyuanDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Fetch Qinyuan purifier data on a schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: QinyuanApiClient,
        *,
        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        """Fetch data from API."""
        try:
            return await self.api.async_get_all_filter_details()
        except QinyuanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except QinyuanApiError as err:
            raise UpdateFailed(str(err)) from err
