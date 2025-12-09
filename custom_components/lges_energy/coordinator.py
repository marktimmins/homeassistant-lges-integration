"""Data update coordinator for LG Energy Solutions."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LGESApiClient, LGESApiError, LGESAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LGESDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching LG Energy Solutions data."""

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
        self._auth_failures = 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            # Authenticate if needed
            if self.client._token_data is None:
                await self.client.authenticate()
                self._auth_failures = 0
            
            # Get all station data
            data = await self.client.get_all_station_data()
            
            if not data:
                _LOGGER.warning("No power stations found for account")
                
            return data
            
        except LGESAuthError as err:
            self._auth_failures += 1
            # Clear token to force re-authentication
            self.client._token_data = None
            
            if self._auth_failures >= 3:
                raise UpdateFailed(f"Authentication failed repeatedly: {err}") from err
                
            _LOGGER.warning("Authentication failed, will retry: %s", err)
            raise UpdateFailed(f"Authentication error: {err}") from err
            
        except LGESApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
