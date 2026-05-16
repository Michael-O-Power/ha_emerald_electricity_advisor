"""BLE client for Emerald Electricity Advisor."""
import asyncio
import logging
from typing import Callable, Optional

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_current_scanners,
)
from homeassistant.core import HomeAssistant

from .const import (
    READ_CHAR_UUID,
    RETURN_30S_POWER_CONSUMPTION_CMD,
    WRITE_CHAR_UUID,
)

_LOGGER = logging.getLogger(__name__)


class EmeraldBLEClient:
    """BLE Client for Emerald Electricity Advisor."""

    def __init__(
        self,
        hass: HomeAssistant,
        ble_address: str,
        pairing_code: int,
        pulses_per_kwh: int,
        on_data_callback: Optional[Callable] = None,
    ):
        """Initialize the BLE client."""
        self.hass = hass
        self.ble_address = ble_address.lower()
        self.pairing_code = pairing_code
        self.pulses_per_kwh = pulses_per_kwh
        self.on_data_callback = on_data_callback
        self.client: Optional[BleakClient] = None
        self.is_connected = False

    async def connect(self, hass: Optional[HomeAssistant] = None) -> bool:
        """Connect to the Emerald device using Home Assistant's tracking framework."""
        try:
            _LOGGER.info(f"Attempting to connect to Emerald device at {self.ble_address}")
            
            if self.client:
                await self.disconnect()

            active_hass = hass or self.hass
            
            # 1. Standard cache check (lowercase)
            ble_device = async_ble_device_from_address(active_hass, self.ble_address.lower(), connectable=True)
            
            # 2. Standard cache check (uppercase)
            if not ble_device:
                ble_device = async_ble_device_from_address(active_hass, self.ble_address.upper(), connectable=True)
            
            # 3. Low-Signal Bypass
            if not ble_device:
                _LOGGER.debug("Device not in standard connectable cache. Attempting historical scanner lookup bypass...")
                for scanner in async_current_scanners(active_hass):
                    discovered = scanner.discovered_devices_and_advertisement_data.get(self.ble_address.upper()) or \
                                 scanner.discovered_devices_and_advertisement_data.get(self.ble_address.lower())
                    if discovered:
                        ble_device = discovered[0]
                        _LOGGER.debug(f"Bypass successful! Recovered device context from scanner source: {scanner.source}")
                        break

            if not ble_device:
                _LOGGER.error(f"Emerald device {self.ble_address} not discovered in HA Bluetooth cache. Signal is likely too weak.")
                self.is_connected = False
                return False

            _LOGGER.debug("Found device context in cache map. Securing connection via bleak-retry-connector.")
            
            self.client = await establish_connection(
                BleakClient,
                ble_device,
                name=f"Emerald_{self.ble_address}",
                disconnected_callback=lambda client: setattr(self, "is_connected", False)
            )

            self.is_connected = True
            _LOGGER.info(f"Connected to Emerald device at {self.ble_address}")

            # Try to establish notifications first before writing commands
            await self._subscribe_to_notifications()
            await self._enable_auto_upload()

            return True
        except BleakError as err:
            _LOGGER.error(f"Failed to connect to Emerald device: {err}")
            await self.disconnect()
            return False
        except asyncio.TimeoutError:
            _LOGGER.error(f"Connection timeout to Emerald device at {self.ble_address}")
            await self.disconnect()
            return False
        except Exception as err:
            _LOGGER.error(f"Unexpected error connecting to Emerald device: {err}")
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        """Disconnect from the Emerald device and explicitly clear the backend instances."""
        if self.client:
            try:
                if self.is_connected:
                    # Cleanly stop any existing notifications before closing down
                    try:
                        await self.client.stop_notify(READ_CHAR_UUID)
                    except Exception:
                        pass
                    await self.client.disconnect()
                _LOGGER.info("Disconnected from Emerald device")
            except BleakError as err:
                _LOGGER.error(f"Error while executing Bleak disconnect: {err}")
            finally:
                self.is_connected = False
                self.client = None

    async def _enable_auto_upload(self) -> None:
        """Enable automatic power data upload from the device."""
        if not self.client or not self.is_connected:
            return
        try:
            enable_auto_upload = bytes.fromhex("0001020b0101")
            await self.client.write_gatt_char(
                WRITE_CHAR_UUID, enable_auto_upload, response=False
            )
            _LOGGER.debug("Auto-upload enabled command written successfully.")
        except BleakError as err:
            _LOGGER.warning(f"Failed to enable auto-upload: {err}")

    async def _subscribe_to_notifications(self) -> None:
        """Subscribe to power consumption notifications with BlueZ lock workarounds."""
        if not self.client or not self.is_connected:
            return
        try:
            await self.client.start_notify(
                READ_CHAR_UUID, self._notification_handler
            )
            _LOGGER.debug("Successfully subscribed to power notifications.")
        except BleakError as err:
            # FIX: Intercept the BlueZ conflict. If notifications are locked or bugged, toggle connection state
            _LOGGER.warning(f"Initial notification subscription failed: {err}. Attempting connection cycle reset workaround...")
            try:
                # Force a manual notification clear/stop routine to drop BlueZ's lock
                await self.client.stop_notify(READ_CHAR_UUID)
                await asyncio.sleep(0.5)
                await self.client.start_notify(READ_CHAR_UUID, self._notification_handler)
                _LOGGER.info("Bypass successful: Subscribed to power notifications after connection cycle reset.")
            except Exception as retry_err:
                _LOGGER.error(f"Bypass failed. Unable to clear BlueZ notification lock: {retry_err}")

    def _notification_handler(self, sender, data: bytearray) -> None:
        """Handle notifications from the device."""
        _LOGGER.debug(f"Raw BLE frame intercepted from advisor: {data.hex()}")
        try:
            parsed_data = self._parse_notification(data)
            if parsed_data and self.on_data_callback:
                _LOGGER.info(f"Parsed updates matching sensor keys: {parsed_data}")
                self.on_data_callback(parsed_data)
        except Exception as err:
            _LOGGER.error(f"Error parsing notification: {err}")

    def _parse_notification(self, data: bytearray) -> Optional[dict]:
        """Parse incoming notification data."""
        if len(data) < 11:
            return None

        command_header = 0
        for i in range(5):
            command_header += data[i] << (8 * (4 - i))

        command_hex = f"{command_header:010x}"

        if command_hex != RETURN_30S_POWER_CONSUMPTION_CMD:
            return None

        timestamp_bin = 0
        for i in range(5, 9):
            timestamp_bin += data[i] << (8 * (8 - i))

        year = 2000 + (timestamp_bin >> 26)
        month = (timestamp_bin >> 22) & 0xF
        day = (timestamp_bin >> 17) & 0x1F
        hour = (timestamp_bin >> 12) & 0x1F
        minute = (timestamp_bin >> 6) & 0x3F
        second = timestamp_bin & 0x3F

        pulses = (data[9] << 8) + data[10]
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
            await asyncio.sleep(0.5)
            return None
        except BleakError as err:
            _LOGGER.error(f"Error getting power: {err}")
            return None
            
