"""Updating the deployed legacy version must not duplicate devices or sensors."""

from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers import area_registry, device_registry, entity_registry

from custom_components.qinyuan.api import QinyuanApiClient
from custom_components.qinyuan.coordinator import QinyuanDataUpdateCoordinator
from custom_components.qinyuan.sensor import QinyuanFilterSensor


async def test_legacy_sensor_keeps_existing_entity_and_device_identity(hass, entry):
    device_registry.async_setup(hass)
    await area_registry.async_load(hass, load_empty=True)
    await device_registry.async_load(hass, load_empty=True)
    await entity_registry.async_load(hass, load_empty=True)
    registry = entity_registry.async_get(hass)
    existing = registry.async_get_or_create(
        "sensor", "qinyuan", "qinyuan_test-device_compound_life", config_entry=entry
    )
    device_registry.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("qinyuan", "test-device")}
    )
    api = QinyuanApiClient(None, "test-account", "A" * 32)
    coordinator = QinyuanDataUpdateCoordinator(hass, entry, api)
    device = {"iotId": "test-iot", "deviceId": "test-device", "productName": "UR-Q5810"}
    detail = {"id": "compound", "name": "Composite filter", "percent": 39}
    coordinator.async_set_updated_data({"test-iot": {"device": device, "filters": [detail]}})
    sensor = QinyuanFilterSensor(coordinator, device, 0, detail)
    assert sensor.unique_id == existing.unique_id
    assert sensor.device_info["identifiers"] == {("qinyuan", "test-device")}
    assert sensor.native_value == 39
    assert sensor.state_class == SensorStateClass.MEASUREMENT

    newly_discovered = QinyuanFilterSensor(
        coordinator, device, 1, {"id": "ro", "name": "RO filter", "percent": 90}
    )
    assert newly_discovered.device_info["identifiers"] == {("qinyuan", "test-device")}
