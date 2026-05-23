"""The Emerald Electricity Advisor integration."""
import asyncio
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import EmeraldDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Emerald Electricity Advisor from a config entry."""
    hass.data.setdefault("emerald_electricity_advisor", {})

    coordinator = EmeraldDataUpdateCoordinator(hass, entry)

    # Await the first manual refresh to establish the initial BLE connection
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data["emerald_electricity_advisor"][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data["emerald_electricity_advisor"].pop(entry.entry_id)
        if coordinator:
            await coordinator.async_shutdown()

    return unload_ok
