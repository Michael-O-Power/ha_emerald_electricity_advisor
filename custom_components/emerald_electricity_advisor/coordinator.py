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
        # 1. Initialize the parent coordinator first so 'hass' is fully attached to the class
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        
        # 2. Pass the fully initialized hass context down into the client
        self.ble_client = EmeraldBLEClient(
            hass=hass,
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

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the device."""
        try:
            if not self.ble_client.is_connected:
                # Pass hass context into the connect method during active runtime loop
                if not await self.ble_client.connect(self.hass):
                    raise UpdateFailed("Failed to connect to Emerald device")

            # Get current power
            power = await self.ble_client.get_power()
            if power is not None:
                # Clone dict to bypass HA memory reference checks
                new_data = dict(self.data)
                new_data["power_watts"] = power
                return new_data

            return self.data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Emerald device: {err}")

    def _on_device_data(self, data: Dict[str, Any]) -> None:
        """Handle data received from the device."""
        # FIX: Clone the dictionary to create a new object in memory. 
        # This forces the HA state machine to trigger the UI redraw listeners!
        new_data = dict(self.data)
        new_data.update(data)
        self.async_set_updated_data(new_data)
        
