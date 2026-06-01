"""Sensors for Qinyuan Smart Water Purifier."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_FILTER_NAME, ATTR_IOT_ID, ATTR_PRODUCT_KEY, DOMAIN
from .coordinator import QinyuanDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qinyuan filter sensors."""
    coordinator: QinyuanDataUpdateCoordinator = entry.runtime_data
    entities: list[QinyuanFilterSensor] = []
    for iot_id, payload in coordinator.data.items():
        device = payload["device"]
        for index, filter_item in enumerate(payload["filters"]):
            entities.append(QinyuanFilterSensor(coordinator, device, index, filter_item))
    async_add_entities(entities)


class QinyuanFilterSensor(CoordinatorEntity[QinyuanDataUpdateCoordinator], SensorEntity):
    """Filter remaining-life sensor."""

    _attr_icon = "mdi:filter"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: QinyuanDataUpdateCoordinator,
        device: dict[str, Any],
        filter_index: int,
        filter_item: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._iot_id = device["iotId"]
        self._product_key = device.get("productKey")
        self._filter_index = filter_index
        self._filter_name = str(filter_item.get("name") or f"Filter {filter_index + 1}")
        device_name = _device_name(device)

        self._attr_name = f"{device_name} {self._filter_name}"
        self._attr_unique_id = f"{DOMAIN}_{self._iot_id}_{filter_index}_{self._filter_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._iot_id)},
            manufacturer="Qinyuan",
            model=device.get("productName") or device.get("productModel") or device.get("model"),
            name=device_name,
        )

    @property
    def native_value(self) -> int | None:
        """Return filter remaining life percentage."""
        filter_item = self._current_filter
        if not filter_item:
            return None
        percent = filter_item.get("percent")
        if percent is None:
            return None
        try:
            return int(percent)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            ATTR_FILTER_NAME: self._filter_name,
            ATTR_IOT_ID: self._iot_id,
            ATTR_PRODUCT_KEY: self._product_key,
        }

    @property
    def _current_filter(self) -> dict[str, Any] | None:
        payload = self.coordinator.data.get(self._iot_id)
        if not payload:
            return None
        filters = payload.get("filters") or []
        if self._filter_index >= len(filters):
            return None
        return filters[self._filter_index]


def _device_name(device: dict[str, Any]) -> str:
    """Return a friendly device name from the cloud payload."""
    return (
        device.get("nickName")
        or device.get("deviceName")
        or device.get("name")
        or device.get("productName")
        or device.get("productModel")
        or device.get("iotId")
        or "Qinyuan"
    )
