"""Updating the deployed legacy version must not duplicate devices or sensors."""

from aiohttp import ClientSession
from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers import area_registry, device_registry, entity_registry

from custom_components.qinyuan.api import QinyuanApiClient
from custom_components.qinyuan.coordinator import QinyuanDataUpdateCoordinator
from custom_components.qinyuan.sensor import QinyuanFilterSensor, async_setup_entry


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


async def test_successful_cloud_filters_reach_all_six_existing_sensors(hass, entry, cloud):
    device_registry.async_setup(hass)
    await area_registry.async_load(hass, load_empty=True)
    await device_registry.async_load(hass, load_empty=True)
    await entity_registry.async_load(hass, load_empty=True)
    registry = entity_registry.async_get(hass)
    devices = [
        {
            "iotId": "test-iot-a",
            "deviceId": "test-device-a",
            "productKey": "test-product-a",
            "productName": "Test purifier A",
        },
        {
            "iotId": "test-iot-b",
            "deviceId": "test-device-b",
            "productKey": "test-product-b",
            "productName": "Test purifier B",
        },
    ]
    expected_ids = set()
    for device in devices:
        device_registry.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={("qinyuan", device["deviceId"])}
        )
        for name in ("composite", "ro", "carbon"):
            unique_id = f"qinyuan_{device['deviceId']}_{name}_life"
            registry.async_get_or_create("sensor", "qinyuan", unique_id, config_entry=entry)
            expected_ids.add(unique_id)
    payloads = [
        {"success": True, "data": {"token": "test-token"}},
        {"success": True, "data": devices},
    ]
    for percentages in ([0, 91, 0], [61, 91, 20]):
        payloads.append(
            {
                "success": True,
                "code": 100,
                "data": {
                    "filterDetail": [
                        {"id": name, "name": name, "percent": percent}
                        for name, percent in zip(
                            ("composite", "ro", "carbon"), percentages, strict=True
                        )
                    ]
                },
            }
        )
    async with cloud(payloads), ClientSession() as session:
        api = QinyuanApiClient(session, "test-account", "A" * 32)
        coordinator = QinyuanDataUpdateCoordinator(hass, entry, api)
        data = await coordinator._async_update_data()
    coordinator.async_set_updated_data(data)
    entry.runtime_data = coordinator
    entities = []
    await async_setup_entry(hass, entry, entities.extend)
    assert len(entities) == 6
    assert {e.unique_id for e in entities} == expected_ids
    assert [e.native_value for e in entities] == [0, 91, 0, 61, 91, 20]
