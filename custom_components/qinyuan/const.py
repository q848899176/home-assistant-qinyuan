"""Constants for the Qinyuan integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "qinyuan"

CONF_PASSWORD_HASH: Final = "password_hash"
CONF_PHONE: Final = "phone"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_APP_VERSION: Final = "2.0.4"
DEFAULT_SCAN_INTERVAL: Final = 3600
DEFAULT_USER_AGENT: Final = "QinYuan/2.0.4 (iPhone; iOS 26.5; Scale/3.00)"
DEFAULT_UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

API_BASE_URL: Final = "https://iot2.qinyuan.cn"
APP_ACCESS_KEY: Final = "1SNc3DS4W65fYLBI03SokWOSwUHcfjV4"
APP_TYPE: Final = "2"

ATTR_FILTER_NAME: Final = "filter_name"
ATTR_IOT_ID: Final = "iot_id"
ATTR_PRODUCT_KEY: Final = "product_key"

DATA_COORDINATOR: Final = "coordinator"
