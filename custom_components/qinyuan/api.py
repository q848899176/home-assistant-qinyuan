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


class QinyuanAccountLockedError(QinyuanAuthError):
    """The cloud account must be unlocked before logging in again."""


def hash_password(password: str) -> str:
    """Hash a password exactly as entered, including significant whitespace."""
    return hashlib.md5(password.encode("utf-8")).hexdigest().upper()


def normalize_password_hash(password: str) -> str:
    """Return the uppercase MD5 password hash used by the Qinyuan app."""
    value = password.strip()
    if len(value) == 32 and all(char in "0123456789abcdefABCDEF" for char in value):
        return value.upper()
    return hash_password(password)


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
        self._auth_error: QinyuanAuthError | None = None

    async def async_login(self) -> str:
        """Login and return a fresh cloud token."""
        if self._auth_error is not None:
            raise self._auth_error
        payload = {
            "accessKey": APP_ACCESS_KEY,
            "appType": APP_TYPE,
            "appVersion": self._app_version,
            "phone": self._phone,
            "password": self._password_hash,
        }
        try:
            data = await self._request("POST", "/web/api/app/user/login", data=payload, auth=False)
            account = data.get("data")
            token = account.get("token") if isinstance(account, dict) else None
            if not isinstance(token, str) or not token:
                raise QinyuanApiError("Qinyuan login returned an incomplete response")
        except QinyuanAuthError as err:
            # Wait for the user to replace credentials instead of locking the account again.
            self._token = None
            self._auth_error = err
            raise
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
        detail = data.get("data")
        if not isinstance(detail, dict):
            raise QinyuanApiError("Unexpected Qinyuan filter detail response")
        filters = detail.get("filterDetail", [])
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
            except QinyuanAuthError:
                raise
            except QinyuanApiError as err:
                _LOGGER.warning("Failed to fetch filter details: %s", err)
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
        if self._auth_error is not None:
            raise self._auth_error
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
                if response.status in (401, 403):
                    data = {"code": response.status}
                else:
                    response.raise_for_status()
                    data = await response.json(content_type=None)
        except ClientResponseError as err:
            raise QinyuanApiError(f"Qinyuan request failed (HTTP {err.status})") from err
        except (ClientError, TimeoutError, ValueError) as err:
            raise QinyuanApiError("Cannot connect to Qinyuan or read its response") from err

        if not isinstance(data, dict):
            raise QinyuanApiError("Unexpected Qinyuan API response")
        code = data.get("code")
        message = str(data.get("msg") or data.get("message") or "").lower()
        failed = data.get("success") is False or code not in (None, 0, "0", 200, "200")
        if code in (144, "144") or (failed and any(word in message for word in ("锁定", "locked"))):
            self._token = None
            self._auth_error = QinyuanAccountLockedError("Qinyuan account is locked")
            raise self._auth_error
        numeric_code = int(code) if str(code).isdigit() else 0
        if numeric_code == 429 or 500 <= numeric_code < 600:
            raise QinyuanApiError("Qinyuan service is temporarily unavailable")
        auth_failed = code in (401, 403, "401", "403", 1001, "1001") or (
            failed
            and any(
                word in message
                for word in (
                    "token",
                    "登录",
                    "授权",
                    "失效",
                    "过期",
                    "密码",
                    "password",
                    "用户名",
                    "账号不存在",
                    "account not found",
                    "invalid credential",
                )
            )
        )
        if auth_failed:
            if auth and retry_auth:
                self._token = None
                await self.async_login()
                return await self._request(method, path, auth=auth, retry_auth=False, **kwargs)
            self._token = None
            self._auth_error = QinyuanAuthError("Qinyuan credentials are invalid or expired")
            raise self._auth_error
        if failed:
            raise QinyuanApiError("Qinyuan rejected the request")
        return data
