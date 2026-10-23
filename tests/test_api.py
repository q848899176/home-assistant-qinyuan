"""Authentication failures must not cause repeated password attempts."""

import pytest
from aiohttp import ClientSession

from custom_components.qinyuan.api import QinyuanApiClient, QinyuanApiError, QinyuanAuthError


@pytest.mark.parametrize(
    "failure",
    [
        {"success": False, "code": 144, "message": "Account locked", "data": 3},
        {"success": False, "message": "Invalid password", "data": 0},
    ],
)
async def test_failed_login_stops_repeated_password_attempts(cloud, failure):
    async with cloud([failure]) as requests, ClientSession() as session:
        client = QinyuanApiClient(session, "test-account", "A" * 32)
        for _ in range(2):
            with pytest.raises(QinyuanAuthError):
                await client.async_login()
        assert len(requests) == 1


@pytest.mark.parametrize(
    "failure",
    [
        503,
        {"success": False, "code": 500, "message": "Service unavailable", "data": 0},
        {"success": True, "data": 3},
        {"success": True, "data": {}},
    ],
)
async def test_transient_failure_does_not_mark_password_invalid(cloud, failure):
    async with cloud([failure, {"success": True, "data": {"token": "test-token"}}]) as requests:
        async with ClientSession() as session:
            client = QinyuanApiClient(session, "test-account", "A" * 32)
            with pytest.raises(QinyuanApiError) as failure:
                await client.async_login()
            assert not isinstance(failure.value, QinyuanAuthError)
            assert await client.async_login() == "test-token"
        assert len(requests) == 2


async def test_lock_from_device_endpoint_stops_all_further_requests(cloud):
    payloads = [
        {"success": True, "data": {"token": "test-token"}},
        {"success": False, "code": 144, "message": "Account locked"},
    ]
    async with cloud(payloads) as requests, ClientSession() as session:
        client = QinyuanApiClient(session, "test-account", "A" * 32)
        for _ in range(2):
            with pytest.raises(QinyuanAuthError):
                await client.async_get_devices()
        assert len(requests) == 2


async def test_expired_token_refreshes_once_and_reads_devices(cloud):
    payloads = [
        {"success": True, "data": {"token": "old-test-token"}},
        {"success": False, "code": 401, "message": "Token expired"},
        {"success": True, "data": {"token": "new-test-token"}},
        {"success": True, "data": [{"iotId": "test-iot"}]},
    ]
    async with cloud(payloads) as requests, ClientSession() as session:
        client = QinyuanApiClient(session, "test-account", "A" * 32)
        assert await client.async_get_devices() == [{"iotId": "test-iot"}]
        assert [r["authorization"] for r in requests] == [
            None,
            "old-test-token",
            None,
            "new-test-token",
        ]
        assert requests[0]["form"]["password"] == "A" * 32


async def test_filter_auth_failure_reaches_home_assistant(cloud):
    payloads = [
        {"success": True, "data": {"token": "test-token"}},
        {"success": True, "data": [{"iotId": "test-iot", "productKey": "test-product"}]},
        {"success": False, "code": 401, "message": "Token expired"},
        {"success": False, "code": 144, "message": "Account locked"},
    ]
    async with cloud(payloads), ClientSession() as session:
        client = QinyuanApiClient(session, "test-account", "A" * 32)
        with pytest.raises(QinyuanAuthError):
            await client.async_get_all_filter_details()


@pytest.mark.parametrize("code", [100, "100"])
async def test_success_code_100_keeps_filter_percentages(cloud, code):
    filters = [
        {
            "id": "composite",
            "percentId": "composite-life",
            "name": "Composite",
            "percent": 0,
            "status": 1,
        },
        {"id": "ro", "percentId": "ro-life", "name": "RO", "percent": 91, "status": 0},
        {"id": "carbon", "percentId": "carbon-life", "name": "Carbon", "percent": 20, "status": 0},
    ]
    payloads = [
        {"success": True, "data": {"token": "test-token"}},
        {"success": True, "data": [{"iotId": "test-iot", "productKey": "test-product"}]},
        {"success": True, "code": code, "data": {"filterDetail": filters}},
    ]
    async with cloud(payloads), ClientSession() as session:
        client = QinyuanApiClient(session, "test-account", "A" * 32)
        values = await client.async_get_all_filter_details()
    assert [f["percent"] for f in values["test-iot"]["filters"]] == [0, 91, 20]


async def test_false_success_with_code_100_is_still_an_error(cloud):
    payloads = [
        {"success": True, "data": {"token": "test-token"}},
        {"success": False, "code": 100, "data": {"filterDetail": [{"percent": 91}]}},
    ]
    async with cloud(payloads), ClientSession() as session:
        client = QinyuanApiClient(session, "test-account", "A" * 32)
        with pytest.raises(QinyuanApiError):
            await client.async_get_filter_detail("test-iot", "test-product")
