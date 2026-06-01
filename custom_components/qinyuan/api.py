"""Client for Qinyuan Smart Connect cloud APIs."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    API_BASE_URL,
    APP_ACCESS_KEY,
    APP_TYPE,
    DEFAULT_APP_VERSION,
    DEFAULT_USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class QinyuanApiError(Exception):
    """Base Qinyuan API error."""


class QinyuanAuthError(QinyuanApiError):
    """Qinyuan authentication error."""


def normalize_password_hash(password: str) -> str:
    """Return the uppercase MD5 password hash used by the Qinyuan app."""
    value = password.strip()
    if len(value) == 32 and all(char in "0123456789abcdefABCDEF" for char in value):
        return value.upper()
    return hashlib.md5(value.encode("utf-8")).hexdigest().upper()


class QinyuanApiClient:
    """Small async API client for Qinyuan cloud."""

    def __init__(
        self,
        session: ClientSession,
        phone: str,
        password_hash: str,
        *,
        app_version: str = DEFAULT_APP_VERSION,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._session = session
        self._phone = phone
        self._password_hash = normalize_password_hash(password_hash)
        self._app_version = app_version
        self._user_agent = user_agent
        self._token: str | None = None

    async def async_login(self) -> str:
        """Login and return a fresh cloud token."""
        payload = {
            "accessKey": APP_ACCESS_KEY,
            "appType": APP_TYPE,
            "appVersion": self._app_version,
            "phone": self._phone,
            "password": self._password_hash,
        }
        data = await self._request("POST", "/web/api/app/user/login", data=payload, auth=False)
        token = data.get("data", {}).get("token")
        if not token:
            raise QinyuanAuthError("Qinyuan login did not return a token")
        self._token = token
        return token

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return devices from Qinyuan account."""
        data = await self._request("GET", "/web/api/app/device/list")
        devices = data.get("data")
        if isinstance(devices, dict):
            devices = devices.get("list") or devices.get("deviceList") or []
        if not isinstance(devices, list):
            raise QinyuanApiError("Unexpected Qinyuan device list response")
        return [device for device in devices if isinstance(device, dict)]

    async def async_get_filter_detail(self, iot_id: str, product_key: str) -> list[dict[str, Any]]:
        """Return filter details for one purifier."""
        data = await self._request(
            "GET",
            "/web/api/app/device/filter/detail",
            params={"iotId": iot_id, "productKey": product_key},
        )
        filters = data.get("data", {}).get("filterDetail", [])
        if not isinstance(filters, list):
            raise QinyuanApiError("Unexpected Qinyuan filter detail response")
        return [filter_item for filter_item in filters if isinstance(filter_item, dict)]

    async def async_get_all_filter_details(self) -> dict[str, dict[str, Any]]:
        """Return all supported purifier filter details keyed by iotId."""
        result: dict[str, dict[str, Any]] = {}
        devices = await self.async_get_devices()
        for device in devices:
            iot_id = device.get("iotId")
            product_key = device.get("productKey")
            if not iot_id or not product_key:
                continue
            try:
                filters = await self.async_get_filter_detail(iot_id, product_key)
            except QinyuanApiError as err:
                _LOGGER.warning("Failed to fetch filter detail for %s: %s", iot_id, err)
                filters = []
            result[iot_id] = {"device": device, "filters": filters}
        return result

    async def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = True,
        retry_auth: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call a Qinyuan API endpoint."""
        if auth and not self._token:
            await self.async_login()

        headers = {"User-Agent": self._user_agent}
        if auth and self._token:
            headers["Authorization"] = self._token

        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=headers,
                timeout=20,
                **kwargs,
            ) as response:
                if response.status in (401, 403) and auth and retry_auth:
                    self._token = None
                    await self.async_login()
                    return await self._request(method, path, auth=auth, retry_auth=False, **kwargs)
                response.raise_for_status()
                data: dict[str, Any] = await response.json(content_type=None)
        except ClientResponseError as err:
            if err.status in (401, 403) and auth and retry_auth:
                self._token = None
                await self.async_login()
                return await self._request(method, path, auth=auth, retry_auth=False, **kwargs)
            raise QinyuanApiError(f"Qinyuan request failed: {err}") from err
        except ClientError as err:
            raise QinyuanApiError(f"Qinyuan request failed: {err}") from err

        code = data.get("code")
        message = data.get("msg") or data.get("message") or "unknown error"
        if code in (401, 403, "401", "403", 1001, "1001"):
            if auth and retry_auth:
                self._token = None
                await self.async_login()
                return await self._request(method, path, auth=auth, retry_auth=False, **kwargs)
            raise QinyuanAuthError(str(message))
        if code not in (None, 0, "0", 200, "200"):
            raise QinyuanApiError(str(message))
        return data
