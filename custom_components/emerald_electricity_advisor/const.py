"""Constants for the Emerald Electricity Advisor integration."""
from typing import Final

DOMAIN: Final = "emerald_electricity_advisor"

# Configuration
CONF_BLE_ADDRESS: Final = "ble_address"
CONF_PULSES_PER_KWH: Final = "pulses_per_kwh"
CONF_NAME: Final = "name"

DEFAULT_NAME: Final = "Emerald Electricity Advisor"
DEFAULT_PULSES_PER_KWH: Final = 1000

# BLE UUIDs from reverse engineering
TIME_SERVICE_UUID: Final = "00001910-0000-1000-8000-00805f9b34fb"
READ_CHAR_UUID: Final = "00002b10-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID: Final = "00002b11-0000-1000-8000-00805f9b34fb"

# Emerald Command Headers
SET_AUTO_UPLOAD_STATUS_CMD: Final = bytes.fromhex("0001020b0101")
RETURN_30S_POWER_CONSUMPTION_CMD: Final = "0001020a06"

# Background check intervals (seconds)
WATCHDOG_INTERVAL: Final = 60
HEARTBEAT_INTERVAL: Final = 300  # 5-minute keep-alive ping
BATTERY_SCAN_INTERVAL: Final = 21600  # Poll battery every 6 hours