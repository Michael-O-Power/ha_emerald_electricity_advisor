"""Data update coordinator for Emerald Electricity Advisor."""
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

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

        # Track the last time we received pushed data
        self.last_data_received = None

        self.ble_client = EmeraldBLEClient(
            hass=hass,
            ble_address=entry.data[CONF_BLE_ADDRESS],
            pairing_code=entry.data[CONF_PAIRING_CODE],
            pulses_per_kwh=entry.data[CONF_PULSES_PER_KWH],
            on_data_callback=self._on_device_data,
            on_disconnect_callback=self._on_disconnect, 
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
        # --- WATCHDOG LOGIC ---
        if self.last_data_received is not None:
            time_since_last = (dt_util.utcnow() - self.last_data_received).total_seconds()
            if time_since_last > 90:
                _LOGGER.error("Watchdog tripped: No data from Emerald for %s seconds. Force killing connection.", time_since_last)
                
                # Forcefully kill the zombie connection (requires a disconnect method in ble_client.py)
                if self.ble_client.is_connected:
                    await self.ble_client.disconnect()
                
                # Reset the timer so we don't spam the logs
                self.last_data_received = None 
                
                # Raising UpdateFailed automatically marks entities as Unavailable
                raise UpdateFailed("Watchdog timeout: No data received for 90 seconds")
        # ---------------------------

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

        # Reset the watchdog timer on every successful data push
        self.last_data_received = dt_util.utcnow()


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
        
    def _on_disconnect(self) -> None:
        """Handle physical BLE disconnection triggered by the client."""
        _LOGGER.warning("Emerald Advisor physically disconnected!")
        
        # Manually flag the coordinator as failed
        self.last_update_success = False
        
        # Force HA to immediately push the 'Unavailable' state to all sensors
        self.async_update_listeners()