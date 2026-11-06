"""LG Energy Solutions (LGES) integration for Home Assistant."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LGESApiClient
from .const import DOMAIN
from .coordinator import LGESDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Every 5 minutes, to stay well clear of the API's rate limits.
SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LG Energy Solutions from a config entry."""
    client = LGESApiClient(
        session=async_get_clientsession(hass),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    coordinator = LGESDataUpdateCoordinator(
        hass=hass,
        client=client,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
