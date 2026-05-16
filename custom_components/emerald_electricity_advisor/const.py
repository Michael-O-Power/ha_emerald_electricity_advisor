"""Constants for the Emerald Electricity Advisor integration."""
from typing import Final

DOMAIN: Final = "emerald_electricity_advisor"

# Configuration
CONF_BLE_ADDRESS: Final = "ble_address"
CONF_PAIRING_CODE: Final = "pairing_code"
CONF_PULSES_PER_KWH: Final = "pulses_per_kwh"
CONF_NAME: Final = "name"

DEFAULT_NAME: Final = "Emerald Electricity Advisor"
DEFAULT_PULSES_PER_KWH: Final = 1000

# BLE UUIDs from reverse engineering
TIME_SERVICE_UUID: Final = "00001910-0000-1000-8000-00805f9b34fb"
READ_CHAR_UUID: Final = "00002b10-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID: Final = "00002b11-0000-1000-8000-00805f9b34fb"

# Emerald Command Headers
GET_IMPULSE_CMD: Final = bytes.fromhex("0001010500")
GET_PAIRING_CODE_CMD: Final = bytes.fromhex("0001030100")
GET_EVERY_30S_POWER_CMD: Final = bytes.fromhex("0001020306")
GET_DEVICE_TIME_CMD: Final = bytes.fromhex("0001010200")
GET_UPDATED_POWER_CMD: Final = bytes.fromhex("0001020100")
SET_IMPULSE_CMD: Final = bytes.fromhex("0001010402")
SET_AUTO_UPLOAD_STATUS_CMD: Final = bytes.fromhex("0001020b0101")

RETURN_30S_POWER_CONSUMPTION_CMD: Final = "0001020a06"
RETURN_UPDATED_POWER_CMD: Final = "0001020204"
RETURN_EVERY_30S_POWER_CMD: Final = "000102050e"

# Update intervals
SCAN_INTERVAL: Final = 30  # seconds