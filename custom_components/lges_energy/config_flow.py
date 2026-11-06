"""Config flow for LG Energy Solutions integration."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LGESApiClient, LGESApiError, LGESAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class LGESConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG Energy Solutions."""

    VERSION = 1

    _reauth_entry: config_entries.ConfigEntry | None = None

    async def _check_login(
        self, username: str, password: str
    ) -> tuple[int, dict[str, str]]:
        """Sign in and count the stations; return (count, errors)."""
        client = LGESApiClient(
            session=async_get_clientsession(self.hass),
            username=username,
            password=password,
        )
        try:
            stations = await client.get_power_stations()
        except LGESAuthError:
            return 0, {"base": "invalid_auth"}
        except LGESApiError:
            return 0, {"base": "cannot_connect"}
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return 0, {"base": "unknown"}
        if not stations:
            return 0, {"base": "no_stations"}
        return len(stations), {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for the account login and check it works."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            count, errors = await self._check_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_create_entry(
                    title=f"LGES Monitor ({count} station{'s' if count > 1 else ''})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Start here when the saved password stops working."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for the new password and check it works."""
        assert self._reauth_entry is not None
        username = self._reauth_entry.data[CONF_USERNAME]
        errors: dict[str, str] = {}

        if user_input is not None:
            _, errors = await self._check_login(username, user_input[CONF_PASSWORD])
            if not errors:
                # (async_update_reload_and_abort needs HA 2024.6; we support 2024.1.)
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={"username": username},
            errors=errors,
        )
