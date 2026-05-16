"""Config flow for Emerald Electricity Advisor integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BLE_ADDRESS,
    CONF_NAME,
    CONF_PAIRING_CODE,
    CONF_PULSES_PER_KWH,
    DEFAULT_NAME,
    DEFAULT_PULSES_PER_KWH,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EmeraldConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Emerald Electricity Advisor."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate BLE address format
            ble_address = user_input[CONF_BLE_ADDRESS].lower()
            if not self._is_valid_ble_address(ble_address):
                errors[CONF_BLE_ADDRESS] = "invalid_ble_address"

            if not errors:
                await self.async_set_unique_id(ble_address)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_BLE_ADDRESS: ble_address,
                        CONF_PAIRING_CODE: user_input[CONF_PAIRING_CODE],
                        CONF_PULSES_PER_KWH: user_input.get(
                            CONF_PULSES_PER_KWH, DEFAULT_PULSES_PER_KWH
                        ),
                        CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_BLE_ADDRESS): str,
                vol.Required(CONF_PAIRING_CODE): int,
                vol.Optional(CONF_PULSES_PER_KWH, default=DEFAULT_PULSES_PER_KWH): int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    def _is_valid_ble_address(address: str) -> bool:
        """Validate BLE address format."""
        parts = address.split(":")
        if len(parts) != 6:
            return False
        try:
            for part in parts:
                if len(part) != 2:
                    return False
                int(part, 16)
            return True
        except ValueError:
            return False
