"""Credential updates keep the existing entry and never expose saved secrets."""

import hashlib
from unittest.mock import Mock

import pytest
from homeassistant.data_entry_flow import AbortFlow

from custom_components.qinyuan.config_flow import QinyuanConfigFlow


def make_flow(hass, entry, source="reconfigure"):
    flow = QinyuanConfigFlow()
    flow.hass = hass
    flow.handler = "qinyuan"
    flow.context = {"source": source, "entry_id": entry.entry_id}
    return flow


async def test_reconfigure_has_password_input_without_saved_secret(hass, entry):
    result = await make_flow(hass, entry).async_step_reconfigure()
    schema = result["data_schema"].schema
    password = next(value for key, value in schema.items() if str(key) == "password")
    assert password.config["type"] == "password"
    assert "A" * 32 not in repr(schema)


@pytest.mark.parametrize("source", ["reconfigure", "reauth"])
@pytest.mark.parametrize("password", ["updated-demo-password", "0" * 32, " spaced-demo-password "])
async def test_new_password_updates_same_entry_and_reloads(
    hass, entry, cloud, monkeypatch, source, password
):
    reload_entry = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", reload_entry)
    flow = make_flow(hass, entry, source)
    if source == "reauth":
        form = await flow.async_step_reauth(entry.data)
        assert form["step_id"] == "reauth_confirm"
        step = flow.async_step_reauth_confirm
    else:
        step = flow.async_step_reconfigure
    payloads = [
        {"success": True, "data": {"token": "test-token"}},
        {"success": True, "data": []},
    ]
    async with cloud(payloads):
        result = await step({"phone": "test-account", "password": password})
    assert result["type"] == "abort"
    assert result["reason"] == source + "_successful"
    assert len(hass.config_entries.async_entries("qinyuan")) == 1
    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
    assert entry.data["password_hash"] == hashlib.md5(password.encode()).hexdigest().upper()
    assert "password" not in entry.data
    assert entry.data["scan_interval"] == 3600
    reload_entry.assert_called_once_with(entry.entry_id)


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"success": False, "code": 144, "message": "Account locked", "data": 1}, "account_locked"),
        ({"success": False, "code": 401, "message": "Invalid password"}, "invalid_auth"),
        (503, "cannot_connect"),
    ],
)
async def test_rejected_credentials_preserve_previous_configuration(
    hass, entry, cloud, payload, error
):
    async with cloud([payload]):
        result = await make_flow(hass, entry).async_step_reconfigure(
            {"phone": "test-account", "password": "wrong-demo-password"}
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": error}
    assert entry.data["password_hash"] == "A" * 32


async def test_reconfigure_cannot_replace_account(hass, entry, cloud):
    async with cloud([]) as requests:
        result = await make_flow(hass, entry).async_step_reconfigure(
            {"phone": "another-test-account", "password": "demo-password"}
        )
    assert result["errors"] == {"phone": "wrong_account"}
    assert not requests
    assert entry.unique_id == "test-account"


async def test_empty_password_does_not_attempt_login(hass, entry, cloud):
    async with cloud([]) as requests:
        result = await make_flow(hass, entry).async_step_reconfigure(
            {"phone": "test-account", "password": ""}
        )
    assert result["errors"] == {"base": "invalid_auth"}
    assert not requests


async def test_legacy_yaml_import_cannot_overwrite_updated_credentials(hass, entry):
    flow = make_flow(hass, entry, "import")
    with pytest.raises(AbortFlow, match="already_configured"):
        await flow.async_step_import({"phone": "test-account", "password_hash": "B" * 32})
    assert entry.data["password_hash"] == "A" * 32


async def test_options_form_works_with_current_home_assistant(hass, entry):
    flow = QinyuanConfigFlow.async_get_options_flow(entry)
    flow.hass = hass
    flow.handler = entry.entry_id
    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["data_schema"]({})["scan_interval"] == 3600
