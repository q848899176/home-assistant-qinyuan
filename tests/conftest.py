"""Real Home Assistant objects with a local cloud API stand-in."""

from collections import deque
from contextlib import asynccontextmanager

import pytest
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.qinyuan import api, config_flow


@pytest.fixture
async def hass(tmp_path, monkeypatch):
    instance = HomeAssistant(str(tmp_path))
    await instance.config.async_set_time_zone("Asia/Shanghai")
    instance.config_entries = ConfigEntries(instance, {})
    async with ClientSession() as session:
        monkeypatch.setattr(config_flow, "async_get_clientsession", lambda _: session)
        yield instance
    await instance.async_stop(force=True)


@pytest.fixture
def entry(hass):
    value = ConfigEntry(
        domain="qinyuan",
        title="Qinyuan",
        data={"phone": "test-account", "password_hash": "A" * 32, "scan_interval": 3600},
        options={},
        source="user",
        unique_id="test-account",
        version=1,
        minor_version=1,
        discovery_keys={},
        subentries_data=None,
    )
    hass.config_entries._entries[value.entry_id] = value
    return value


@pytest.fixture
def cloud(monkeypatch):
    @asynccontextmanager
    async def serve(payloads):
        responses = deque(payloads)
        requests = []

        async def handle(request):
            requests.append(
                {
                    "path": request.path,
                    "authorization": request.headers.get("Authorization"),
                    "form": dict(await request.post()),
                }
            )
            if not responses:
                return web.json_response({"message": "Unexpected extra request"}, status=500)
            payload = responses.popleft()
            if isinstance(payload, int):
                return web.json_response({"message": "Service unavailable"}, status=payload)
            return web.json_response(payload)

        app = web.Application()
        app.router.add_route("*", "/{path:.*}", handle)
        async with TestServer(app) as server:
            monkeypatch.setattr(api, "API_BASE_URL", str(server.make_url("/")).rstrip("/"))
            yield requests

    return serve
