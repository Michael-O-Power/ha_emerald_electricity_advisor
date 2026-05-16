"""Sensor platform for Emerald Electricity Advisor."""
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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

    sensors = [
        EmeraldPowerSensor(coordinator, config_entry),
        EmeraldEnergySensor(coordinator, config_entry),
        EmeraldPulsesSensor(coordinator, config_entry),
    ]

    async_add_entities(sensors)


class EmeraldSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Emerald sensors."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.config_entry.data.get(CONF_NAME, "Emerald Electricity Advisor"),
            manufacturer="Emerald",
            model="Electricity Advisor",
        )


class EmeraldPowerSensor(EmeraldSensorBase):
    """Sensor for power consumption."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Power"
        # FIX: Explicit unique ID construction without pulling missing entity descriptions
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data.get("power_watts")


class EmeraldEnergySensor(EmeraldSensorBase):
    """Sensor for energy consumption."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Energy"
        # FIX: Explicit unique ID construction
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:lightning-bolt-circle"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data.get("energy_kwh")


class EmeraldPulsesSensor(EmeraldSensorBase):
    """Sensor for pulse count."""

    def __init__(
        self,
        coordinator: EmeraldDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the pulses sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Pulses"
        # FIX: Explicit unique ID construction
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_pulses"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:pulse"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data.get("pulses")
        
