"""Sensor platform for Emerald Electricity Advisor."""
import logging
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_NAME, DOMAIN
from .coordinator import EmeraldDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Emerald Electricity Advisor sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Initialize the new daily tracking sensor first so we can pass it to the Yesterday sensor
    today_sensor = EmeraldEnergyTodaySensor(coordinator, config_entry)

    sensors = [
        EmeraldPowerSensor(coordinator, config_entry),
        EmeraldEnergySensor(coordinator, config_entry),
        EmeraldPulsesSensor(coordinator, config_entry),
        EmeraldBatterySensor(coordinator, config_entry),
        today_sensor,
        EmeraldEnergyYesterdaySensor(coordinator, config_entry, today_sensor),
    ]

    async_add_entities(sensors)


class EmeraldSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Emerald sensors with Event Bus Optimization."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
        data_key: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.data_key = data_key  # The dictionary key from the coordinator data

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.config_entry.data.get(CONF_NAME, "Emerald Electricity Advisor"),
            manufacturer="Emerald",
            model="Electricity Advisor",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update native value efficiently when the coordinator receives new data."""
        if self.data_key and self.coordinator.data is not None:
            self._attr_native_value = self.coordinator.data.get(self.data_key)
        super()._handle_coordinator_update()


class EmeraldPowerSensor(EmeraldSensorBase):
    """Sensor for live power consumption."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(coordinator, config_entry, data_key="power_watts")
        self._attr_name = "Power"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:lightning-bolt"


class EmeraldEnergySensor(EmeraldSensorBase):
    """Sensor for lifetime energy consumption."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(coordinator, config_entry, data_key="energy_kwh")
        self._attr_name = "Energy"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:lightning-bolt-circle"


class EmeraldPulsesSensor(EmeraldSensorBase):
    """Sensor for lifetime pulse count."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the pulses sensor."""
        super().__init__(coordinator, config_entry, data_key="pulses")
        self._attr_name = "Pulses"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_pulses"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:pulse"


class EmeraldBatterySensor(EmeraldSensorBase):
    """Sensor for battery level."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, config_entry, data_key="battery_level")
        self._attr_name = "Battery"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_battery"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT


class EmeraldEnergyTodaySensor(EmeraldSensorBase, RestoreEntity):
    """Robust sensor that tracks energy consumption today, immune to restarts."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the daily energy tracker."""
        super().__init__(coordinator, config_entry, data_key=None)
        self._attr_name = "Energy Consumption Today"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_energy_today"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:calendar-today"
        
        self._attr_native_value = 0.0
        self._midnight_baseline: float | None = None
        self._current_date: date | None = None
        self._last_valid_energy: float | None = None
        
        # We store yesterday's total here so the Yesterday sensor can grab it without race conditions
        self.yesterday_total: float = 0.0

    async def async_added_to_hass(self) -> None:
        """Restore previous state and baselines if Home Assistant restarts."""
        await super().async_added_to_hass()
        
        if (old_state := await self.async_get_last_state()) is not None:
            try:
                self._attr_native_value = float(old_state.state) if old_state.state not in (None, "unknown", "unavailable") else 0.0
                if "midnight_baseline" in old_state.attributes:
                    self._midnight_baseline = float(old_state.attributes["midnight_baseline"])
                if "current_date" in old_state.attributes:
                    self._current_date = date.fromisoformat(old_state.attributes["current_date"])
                if "yesterday_total" in old_state.attributes:
                    self.yesterday_total = float(old_state.attributes["yesterday_total"])
            except (ValueError, TypeError):
                self._attr_native_value = 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Save baseline state out to the registry state attributes for restoration."""
        return {
            "midnight_baseline": self._midnight_baseline,
            "current_date": self._current_date.isoformat() if self._current_date else None,
            "yesterday_total": self.yesterday_total,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Calculate daily usage on every coordinator update tick."""
        if self.coordinator.data is None:
            return

        raw_energy = self.coordinator.data.get("energy_kwh")
        if raw_energy is None:
            return

        try:
            current_energy = float(raw_energy)
        except (ValueError, TypeError):
            return

        # Handle API Dropouts: Ignore 0.0 if we previously had a valid reading
        if current_energy == 0.0 and self._last_valid_energy is not None and self._last_valid_energy > 0:
            _LOGGER.warning("Emerald API returned 0.0 kWh. Ignoring potential glitch.")
            return

        self._last_valid_energy = current_energy
        now_date = dt_util.now().date()

        # Initialization
        if self._current_date is None:
            self._current_date = now_date
        if self._midnight_baseline is None:
            self._midnight_baseline = current_energy

        # Missed Midnight / Date Rollover Check
        if now_date != self._current_date:
            _LOGGER.debug("Emerald date rollover detected. Archiving yesterday's total.")
            self.yesterday_total = float(self._attr_native_value or 0.0)
            self._midnight_baseline = current_energy
            self._attr_native_value = 0.0
            self._current_date = now_date
        
        # Calculate Delta
        if current_energy >= self._midnight_baseline:
            self._attr_native_value = round(current_energy - self._midnight_baseline, 3)
        else:
            # The physical meter reset, adjust baseline but don't wipe out today's accumulation
            _LOGGER.info("Emerald meter reset detected. Adjusting baseline tracking.")
            self._midnight_baseline = current_energy

        super()._handle_coordinator_update()


class EmeraldEnergyYesterdaySensor(EmeraldSensorBase, RestoreEntity):
    """Sensor that locks and shows yesterday's total aggregated daily usage."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
        today_sensor: EmeraldEnergyTodaySensor,
    ) -> None:
        """Initialize yesterday's final energy tracker."""
        super().__init__(coordinator, config_entry, data_key=None)
        self._today_sensor = today_sensor
        self._attr_name = "Daily Power Consumption Yesterday"
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_energy_yesterday"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:history"
        
        self._attr_native_value = 0.0

    async def async_added_to_hass(self) -> None:
        """Handle restoration."""
        await super().async_added_to_hass()
        
        if (old_state := await self.async_get_last_state()) is not None:
            try:
                self._attr_native_value = float(old_state.state) if old_state.state not in (None, "unknown", "unavailable") else 0.0
            except (ValueError, TypeError):
                self._attr_native_value = 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fetch the locked yesterday value from the Today sensor."""
        # By reading the variable stored in the today_sensor, we avoid race conditions
        # and guarantee we always have the exact value locked in at midnight.
        self._attr_native_value = round(self._today_sensor.yesterday_total, 3)
        super()._handle_coordinator_update()
