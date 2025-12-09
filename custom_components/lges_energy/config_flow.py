"""Config flow for LG Energy Solutions integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LGESApiClient, LGESAuthError, LGESApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class LGESConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG Energy Solutions."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Test authentication
                session = async_get_clientsession(self.hass)
                client = LGESApiClient(
                    session=session,
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                
                await client.authenticate()
                
                # Get stations to validate we have access
                stations = await client.get_power_stations()
                
                if not stations:
                    errors["base"] = "no_stations"
                else:
                    # Create unique ID based on username
                    await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                    self._abort_if_unique_id_configured()
                    
                    # Get station info for title
                    station_count = len(stations)
                    title = f"LGES Monitor ({station_count} station{'s' if station_count > 1 else ''})"
                    
                    return self.async_create_entry(
                        title=title,
                        data=user_input,
                    )
                    
            except LGESAuthError:
                errors["base"] = "invalid_auth"
            except LGESApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class LGESOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for LG Energy Solutions."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
