"""Data update coordinator for Emerald Electricity Advisor."""
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry

from .ble_client import EmeraldBLEClient
from .const import (
    CONF_BLE_ADDRESS,
    CONF_PAIRING_CODE,
    CONF_PULSES_PER_KWH,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class EmeraldDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Emerald data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data update coordinator."""
        self.ble_client = EmeraldBLEClient(
            ble_address=entry.data[CONF_BLE_ADDRESS],
            pairing_code=entry.data[CONF_PAIRING_CODE],
            pulses_per_kwh=entry.data[CONF_PULSES_PER_KWH],
            on_data_callback=self._on_device_data,
        )
        self.entry = entry
        self.data: Dict[str, Any] = {
            "power_watts": 0,
            "energy_kwh": 0,
            "pulses": 0,
            "timestamp": None,
        }

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the device."""
        try:
            if not self.ble_client.is_connected:
                if not await self.ble_client.connect():
                    raise UpdateFailed("Failed to connect to Emerald device")

            # Get current power
            power = await self.ble_client.get_power()
            if power is not None:
                self.data["power_watts"] = power

            return self.data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Emerald device: {err}")

    def _on_device_data(self, data: Dict[str, Any]) -> None:
        """Handle data received from the device."""
        self.data.update(data)
        # Notify listeners that data has been updated
        self.async_set_updated_data(self.data)