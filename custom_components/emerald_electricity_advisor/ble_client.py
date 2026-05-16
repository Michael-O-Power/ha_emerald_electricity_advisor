"""BLE client for Emerald Electricity Advisor."""
import asyncio
import logging
from typing import Callable, Optional

from bleak import BleakClient, BleakError
from bleak.discover import discover

from .const import (
    READ_CHAR_UUID,
    RETURN_30S_POWER_CONSUMPTION_CMD,
    RETURN_UPDATED_POWER_CMD,
    SET_AUTO_UPLOAD_STATUS_CMD,
    TIME_SERVICE_UUID,
    WRITE_CHAR_UUID,
)

_LOGGER = logging.getLogger(__name__)


class EmeraldBLEClient:
    """BLE Client for Emerald Electricity Advisor."""

    def __init__(
        self,
        ble_address: str,
        pairing_code: int,
        pulses_per_kwh: int,
        on_data_callback: Optional[Callable] = None,
    ):
        """Initialize the BLE client."""
        self.ble_address = ble_address.lower()
        self.pairing_code = pairing_code
        self.pulses_per_kwh = pulses_per_kwh
        self.on_data_callback = on_data_callback
        self.client: Optional[BleakClient] = None
        self.is_connected = False

    async def connect(self) -> bool:
        """Connect to the Emerald device."""
        try:
            _LOGGER.info(f"Attempting to connect to Emerald device at {self.ble_address}")
            
            # Try to discover the device first
            _LOGGER.debug("Scanning for available BLE devices...")
            try:
                devices = await discover(timeout=5.0)
                
                device_found = False
                _LOGGER.debug(f"Found {len(devices)} BLE devices:")
                for device in devices:
                    _LOGGER.debug(f"  - {device.address}: {device.name}")
                    if device.address.lower() == self.ble_address:
                        device_found = True
                        _LOGGER.info(f"Found Emerald device: {device.name} ({device.address})")
                
                if not device_found:
                    _LOGGER.warning(f"Device {self.ble_address} not found in BLE scan")
                    _LOGGER.warning("Make sure the device is powered on and in range")
            except Exception as discover_err:
                _LOGGER.warning(f"Could not scan for devices: {discover_err}")
                _LOGGER.info("Attempting direct connection...")
            
            # Attempt connection regardless (device might be cached)
            self.client = BleakClient(self.ble_address, timeout=10.0)
            await self.client.connect()
            self.is_connected = True
            _LOGGER.info(f"Connected to Emerald device at {self.ble_address}")

            # Enable auto-upload
            await self._enable_auto_upload()

            # Subscribe to notifications
            await self._subscribe_to_notifications()

            return True
        except BleakError as err:
            _LOGGER.error(f"Failed to connect to Emerald device: {err}")
            self.is_connected = False
            return False
        except asyncio.TimeoutError:
            _LOGGER.error(f"Connection timeout to Emerald device at {self.ble_address}")
            self.is_connected = False
            return False
        except Exception as err:
            _LOGGER.error(f"Unexpected error connecting to Emerald device: {err}")
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the Emerald device."""
        if self.client and self.is_connected:
            try:
                await self.client.disconnect()
                self.is_connected = False
                _LOGGER.info("Disconnected from Emerald device")
            except BleakError as err:
                _LOGGER.error(f"Error disconnecting: {err}")

    async def _enable_auto_upload(self) -> None:
        """Enable automatic power data upload from the device."""
        try:
            enable_auto_upload = bytes.fromhex("0001020b0101")
            await self.client.write_gatt_char(
                WRITE_CHAR_UUID, enable_auto_upload, response=False
            )
            _LOGGER.debug("Auto-upload enabled")
        except BleakError as err:
            _LOGGER.warning(f"Failed to enable auto-upload: {err}")

    async def _subscribe_to_notifications(self) -> None:
        """Subscribe to power consumption notifications."""
        try:
            await self.client.start_notify(
                READ_CHAR_UUID, self._notification_handler
            )
            _LOGGER.debug("Subscribed to power notifications")
        except BleakError as err:
            _LOGGER.warning(f"Failed to subscribe to notifications: {err}")

    def _notification_handler(self, sender, data: bytearray) -> None:
        """Handle notifications from the device."""
        try:
            parsed_data = self._parse_notification(data)
            if parsed_data and self.on_data_callback:
                self.on_data_callback(parsed_data)
        except Exception as err:
            _LOGGER.error(f"Error parsing notification: {err}")

    def _parse_notification(self, data: bytearray) -> Optional[dict]:
        """Parse incoming notification data."""
        if len(data) < 11:
            return None

        # Extract command header (first 5 bytes)
        command_header = 0
        for i in range(5):
            command_header += data[i] << (8 * (4 - i))

        command_hex = f"{command_header:010x}"

        # Only process 30s power consumption updates
        if command_hex != RETURN_30S_POWER_CONSUMPTION_CMD:
            return None

        # Parse timestamp (bytes 5-8)
        timestamp_bin = 0
        for i in range(5, 9):
            timestamp_bin += data[i] << (8 * (8 - i))

        # Parse timestamp components
        year = 2000 + (timestamp_bin >> 26)
        month = (timestamp_bin >> 22) & 0xF
        day = (timestamp_bin >> 17) & 0x1F
        hour = (timestamp_bin >> 12) & 0x1F
        minute = (timestamp_bin >> 6) & 0x3F
        second = timestamp_bin & 0x3F

        # Extract pulses (bytes 9-10)
        pulses = (data[9] << 8) + data[10]

        # Calculate power in watts
        # power = (pulses / pulses_per_kwh) * 3600 * 1000 / 30
        # Simplified: power = (pulses * 120000) / pulses_per_kwh
        power_watts = (pulses * 120000) / self.pulses_per_kwh

        return {
            "timestamp": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}",
            "pulses": pulses,
            "power_watts": power_watts,
            "energy_kwh": pulses / self.pulses_per_kwh,
        }

    async def get_power(self) -> Optional[float]:
        """Get current power consumption."""
        if not self.is_connected or not self.client:
            return None

        try:
            cmd = bytes.fromhex("0001020100")
            await self.client.write_gatt_char(WRITE_CHAR_UUID, cmd, response=False)
            await asyncio.sleep(0.5)  # Wait for response
            return None  # Will be populated via notification
        except BleakError as err:
            _LOGGER.error(f"Error getting power: {err}")
            return None
