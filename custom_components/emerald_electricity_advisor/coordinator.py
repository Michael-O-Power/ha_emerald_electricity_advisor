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
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        
        self.ble_client = EmeraldBLEClient(
            hass=hass,
            ble_address=entry.data[CONF_BLE_ADDRESS],
            pairing_code=entry.data[CONF_PAIRING_CODE],
            pulses_per_kwh=entry.data[CONF_PULSES_PER_KWH],
            on_data_callback=self._on_device_data,
        )
        self.entry = entry
        
        # Initialize running totals to satisfy HA's TOTAL_INCREASING state class requirements
        self.total_pulses = 0
        self.total_energy_kwh = 0.0
        
        self.data: Dict[str, Any] = {
            "power_watts": 0,
            "energy_kwh": 0.0,
            "pulses": 0,
            "battery_level": None,
            "timestamp": None,
        }

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the device."""
        try:
            if not self.ble_client.is_connected:
                if not await self.ble_client.connect(self.hass):
                    raise UpdateFailed("Failed to connect to Emerald device")

            # Get current power and battery
            power = await self.ble_client.get_power()
            battery = await self.ble_client.get_battery()
            
            new_data = dict(self.data)
            if power is not None:
                new_data["power_watts"] = power
            if battery is not None:
                new_data["battery_level"] = battery
                
            return new_data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with Emerald device: {err}")

    def _on_device_data(self, data: Dict[str, Any]) -> None:
        """Handle data received from the device."""
        # Clone the dictionary to create a new object in memory, bypassing HA reference checks
        new_data = dict(self.data)
        
        # The device broadcasts energy/pulses consumed in a 30-second window.
        # We accumulate these into a running tally for the long-term statistics database.
        if "pulses" in data:
            self.total_pulses += data["pulses"]
            new_data["pulses"] = self.total_pulses
            
        if "energy_kwh" in data:
            self.total_energy_kwh += data["energy_kwh"]
            new_data["energy_kwh"] = self.total_energy_kwh
            
        if "power_watts" in data:
            new_data["power_watts"] = data["power_watts"]
            
        if "timestamp" in data:
            new_data["timestamp"] = data["timestamp"]

        self.async_set_updated_data(new_data)
        
