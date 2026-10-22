"""Sensors for Qinyuan Smart Water Purifier."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
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
    for payload in coordinator.data.values():
        device = payload["device"]
        for index, filter_item in enumerate(payload["filters"]):
            entities.append(QinyuanFilterSensor(coordinator, device, index, filter_item))
    async_add_entities(entities)


class QinyuanFilterSensor(CoordinatorEntity[QinyuanDataUpdateCoordinator], SensorEntity):
    """Filter remaining-life sensor."""

    _attr_icon = "mdi:filter"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0
    _attr_state_class = SensorStateClass.MEASUREMENT

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
        device_identifier = self._iot_id
        # Early installations used deviceId and cloud filter IDs; keep their registry identities.
        legacy_device_id = device.get("deviceId") or self._iot_id
        devices = dr.async_entries_for_config_entry(
            dr.async_get(coordinator.hass), coordinator.config_entry.entry_id
        )
        if any((DOMAIN, legacy_device_id) in registered.identifiers for registered in devices):
            device_identifier = legacy_device_id
        filter_id = str(filter_item.get("id") or filter_item.get("percentId") or filter_index + 1)
        filter_slug = re.sub(r"[^0-9a-zA-Z_]+", "_", filter_id).strip("_").lower() or "filter"
        legacy_id = f"qinyuan_{legacy_device_id}_{filter_slug}_life"
        registry = er.async_get(coordinator.hass)
        if not registry.async_get_entity_id(
            "sensor", DOMAIN, self._attr_unique_id
        ) and registry.async_get_entity_id("sensor", DOMAIN, legacy_id):
            self._attr_unique_id = legacy_id
            device_identifier = legacy_device_id
        if device_identifier == legacy_device_id:
            self._attr_has_entity_name = True
            self._attr_name = self._filter_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_identifier)},
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
        except TypeError, ValueError:
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
