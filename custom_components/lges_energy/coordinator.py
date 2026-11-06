"""Data update coordinator for LG Energy Solutions."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LGESApiClient, LGESApiError, LGESAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LGESDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches data for every station on the account."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: LGESApiClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API (the client signs in again when needed)."""
        try:
            data = await self.client.get_all_station_data()
        except LGESAuthError as err:
            # Stops polling (so a wrong password isn't retried every update)
            # and asks the user to sign in again.
            raise ConfigEntryAuthFailed(str(err)) from err
        except LGESApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        if not data:
            _LOGGER.warning("No power stations found for account")
        return data
