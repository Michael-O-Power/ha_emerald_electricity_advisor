 
"""Data update coordinator for Emerald Electricity Advisor."""
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .ble_client import EmeraldBLEClient
from .const import (
    CONF_BLE_ADDRESS,
    CONF_PULSES_PER_KWH,
    DOMAIN,
    WATCHDOG_INTERVAL,
    BATTERY_SCAN_INTERVAL,
    HEARTBEAT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class EmeraldDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage push-based data from the Emerald device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the push coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )

        self.last_data_received = None
        self.entry = entry

        self.ble_client = EmeraldBLEClient(
            hass=hass,
            ble_address=entry.data[CONF_BLE_ADDRESS],
            pulses_per_kwh=entry.data[CONF_PULSES_PER_KWH],
            on_data_callback=self._on_device_data,
            on_disconnect_callback=self._on_disconnect, 
        )
        
        # Tracking listeners
        self._unsub_watchdog = None
        self._unsub_battery = None
        self._unsub_heartbeat = None
        
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
        """Fetch initial data and establish the persistent BLE connection."""
        try:
            if not self.ble_client.is_connected:
                if not await self.ble_client.connect(self.hass):
                    raise UpdateFailed("Failed to connect to Emerald device")

                # Setup background protection tasks now that we are connected
                if not self._unsub_watchdog:
                    self._unsub_watchdog = async_track_time_interval(
                        self.hass, self._async_watchdog_check, timedelta(seconds=WATCHDOG_INTERVAL)
                    )
                if not self._unsub_heartbeat:
                    self._unsub_heartbeat = async_track_time_interval(
                        self.hass, self._async_send_heartbeat, timedelta(seconds=HEARTBEAT_INTERVAL)
                    )
                if not self._unsub_battery:
                    self._unsub_battery = async_track_time_interval(
                        self.hass, self._async_update_battery, timedelta(seconds=BATTERY_SCAN_INTERVAL)
                    )

            # Grab an initial baseline battery read
            battery = await self.ble_client.get_battery()
            if battery is not None:
                self.data["battery_level"] = battery
                
            return self.data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with Emerald device: {err}")

    async def _async_send_heartbeat(self, now: Any) -> None:
        """Periodic keep-alive ping to prevent device sleep."""
        if self.ble_client.is_connected:
            await self.ble_client.send_heartbeat()

    async def _async_watchdog_check(self, now: Any) -> None:
        """Independent loop to verify the push stream hasn't died silently."""
        if self.last_data_received is not None:
            time_since_last = (dt_util.utcnow() - self.last_data_received).total_seconds()
            if time_since_last > 90:
                _LOGGER.error(f"Watchdog tripped: No data from Emerald for {time_since_last} seconds. Forcing reconnect.")
                
                if self.ble_client.is_connected:
                    await self.ble_client.disconnect()
                
                self.last_data_received = None 
                self._on_disconnect()
                
                # Attempt to restart the connection in the background
                self.hass.async_create_task(self.ble_client.connect(self.hass))

    async def _async_update_battery(self, now: Any) -> None:
        """Infrequent battery poll to save device lifespan."""
        if self.ble_client.is_connected:
            battery = await self.ble_client.get_battery()
            if battery is not None:
                new_data = dict(self.data)
                new_data["battery_level"] = battery
                self.async_set_updated_data(new_data)

    def _on_device_data(self, data: Dict[str, Any]) -> None:
        """Handle pushed data from the Bleak background thread."""
        # Safely bounce execution off the Bleak background thread and onto HA's main event loop
        self.hass.loop.call_soon_threadsafe(self._async_process_device_data, data)

    @callback
    def _async_process_device_data(self, data: Dict[str, Any]) -> None:
        """Process data safely on the Home Assistant main event loop with deduplication."""
        # Check the hardware-generated timestamp from the BLE payload against our last recorded state
        if data.get("timestamp") == self.data.get("timestamp"):
            _LOGGER.debug("Dropped duplicate Emerald BLE packet for timestamp: %s", data.get("timestamp"))
            return

        self.last_data_received = dt_util.utcnow()
        new_data = dict(self.data)
        
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
        """Handle physical BLE disconnection safely."""
        self.last_update_success = False
        self.hass.loop.call_soon_threadsafe(self.async_update_listeners)

    async def async_shutdown(self) -> None:
        """Clean up tasks and connection on integration unload."""
        if self._unsub_watchdog:
            self._unsub_watchdog()
        if self._unsub_heartbeat:
            self._unsub_heartbeat()
        if self._unsub_battery:
            self._unsub_battery()
            
        if self.ble_client.is_connected:
            await self.ble_client.disconnect()
