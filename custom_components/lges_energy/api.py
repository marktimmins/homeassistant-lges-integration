"""API client for LG Energy Solutions SEMS Portal."""
from __future__ import annotations

import base64
import json
import logging
from typing import Any

import aiohttp

from .const import (
    DEFAULT_API_BASE,
    EMPTY_TOKEN_DATA,
    GET_CHART_ENDPOINT,
    GET_PLANT_DETAIL_ENDPOINT,
    GET_POWERFLOW_ENDPOINT,
    GET_STATIONS_ENDPOINT,
    LOGIN_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class LGESApiError(Exception):
    """Exception for LGES API errors."""


class LGESAuthError(LGESApiError):
    """Exception for authentication errors."""


class LGESApiClient:
    """API client for LG Energy Solutions SEMS Portal."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        api_base: str = DEFAULT_API_BASE,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self._api_base = api_base
        self._token_data: dict[str, Any] | None = None
        self._uid: str | None = None

    def _encode_token(self, token_data: dict[str, Any]) -> str:
        """Encode token data to base64 string."""
        # Remove whitespace and encode
        json_str = json.dumps(token_data, separators=(',', ':'))
        return base64.b64encode(json_str.encode()).decode()

    def _get_empty_token(self) -> str:
        """Get the empty token for unauthenticated requests."""
        return self._encode_token(EMPTY_TOKEN_DATA)

    def _get_auth_token(self) -> str:
        """Get the authenticated token."""
        if not self._token_data:
            raise LGESAuthError("Not authenticated")
        return self._encode_token(self._token_data)

    def _get_headers(self, authenticated: bool = True) -> dict[str, str]:
        """Get headers for API request."""
        token = self._get_auth_token() if authenticated else self._get_empty_token()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "token": token,
            "neutral": "4",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    async def _request(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """Make an API request."""
        url = f"{self._api_base}{endpoint}"
        headers = self._get_headers(authenticated)
        
        try:
            async with self._session.post(
                url,
                json=data or {},
                headers=headers,
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                if result.get("hasError"):
                    error_msg = result.get("msg", "Unknown error")
                    _LOGGER.error("API error: %s", error_msg)
                    raise LGESApiError(error_msg)
                
                return result
                
        except aiohttp.ClientError as err:
            _LOGGER.error("API request failed: %s", err)
            raise LGESApiError(f"Request failed: {err}") from err

    async def authenticate(self) -> bool:
        """Authenticate with the SEMS portal."""
        _LOGGER.debug("Authenticating with SEMS portal")
        
        login_data = {
            "account": self._username,
            "pwd": self._password,
            "agreement_agreement": 0,
            "is_local": False,
        }
        
        try:
            result = await self._request(
                LOGIN_ENDPOINT,
                data=login_data,
                authenticated=False,
            )
            
            data = result.get("data", {})
            self._token_data = {
                "uid": data.get("uid", ""),
                "timestamp": data.get("timestamp", 0),
                "token": data.get("token", ""),
                "client": data.get("client", "web"),
                "version": data.get("version", ""),
                "language": data.get("language", "en"),
            }
            self._uid = data.get("uid")
            
            # Check if we got a redirect to a different API endpoint
            if "api" in result:
                new_api = result["api"]
                if new_api and new_api != self._api_base:
                    _LOGGER.info("Using redirected API: %s", new_api)
                    self._api_base = new_api
            
            _LOGGER.debug("Authentication successful for user %s", self._username)
            return True
            
        except LGESApiError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise LGESAuthError(f"Authentication failed: {err}") from err

    async def get_power_stations(self) -> list[dict[str, Any]]:
        """Get list of power stations for the authenticated user."""
        if not self._token_data:
            await self.authenticate()
        
        result = await self._request(GET_STATIONS_ENDPOINT, data={})
        
        # The API may return a single station ID as a string or a list
        data = result.get("data")
        
        if isinstance(data, str):
            # Single station - wrap in list
            return [{"id": data}]
        elif isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Might be a dict with station info
            if "id" in data:
                return [data]
            # Or might be keyed by ID
            return [{"id": k, **v} for k, v in data.items()]
        else:
            _LOGGER.warning("Unexpected station data format: %s", type(data))
            return []

    async def get_plant_details(self, station_id: str) -> dict[str, Any]:
        """Get detailed plant information for a power station."""
        if not self._token_data:
            await self.authenticate()
        
        result = await self._request(
            GET_PLANT_DETAIL_ENDPOINT,
            data={"PowerStationId": station_id, "powerstation_id": station_id},
        )
        
        return result.get("data", {})

    async def get_powerflow(self, station_id: str) -> dict[str, Any]:
        """Get current power flow data for a power station."""
        if not self._token_data:
            await self.authenticate()
        
        result = await self._request(
            GET_POWERFLOW_ENDPOINT,
            data={"PowerStationId": station_id, "powerstation_id": station_id},
        )
        
        return result.get("data", {})

    async def get_chart_data(self, station_id: str, date: str) -> dict[str, Any]:
        """Get chart/historical data for a power station."""
        if not self._token_data:
            await self.authenticate()
        
        result = await self._request(
            GET_CHART_ENDPOINT,
            data={
                "id": station_id,
                "date": date,
                "full_script": False,
            },
        )
        
        return result.get("data", {})

    async def get_daily_energy_stats(self, station_id: str, date: str) -> dict[str, Any]:
        """Get daily energy statistics (buy/sell/charge/discharge) for a power station.
        
        Uses GetChartByPlant with chartIndexId=7 and Range=2 to get daily totals.
        """
        if not self._token_data:
            await self.authenticate()
        
        # Import here to get the endpoint constant
        from .const import GET_CHART_BY_PLANT_ENDPOINT
        
        result = await self._request(
            GET_CHART_BY_PLANT_ENDPOINT,
            data={
                "Id": station_id,
                "Date": date,
                "Range": "2",  # Day
                "ChartIndexId": "7",  # Energy statistics
                "IsDetailFull": False,
            },
        )
        
        return result.get("data", {})

    async def get_monthly_energy_stats(self, station_id: str, date: str) -> dict[str, Any]:
        """Get monthly energy statistics (buy/sell/charge/discharge) for a power station.
        
        Uses GetChartByPlant with chartIndexId=7 and Range=3 to get monthly totals.
        The month is determined by the provided date.
        """
        if not self._token_data:
            await self.authenticate()
        
        # Import here to get the endpoint constant
        from .const import GET_CHART_BY_PLANT_ENDPOINT
        
        result = await self._request(
            GET_CHART_BY_PLANT_ENDPOINT,
            data={
                "Id": station_id,
                "Date": date,
                "Range": "3",  # Month
                "ChartIndexId": "7",  # Energy statistics
                "IsDetailFull": False,
            },
        )
        
        return result.get("data", {})

    async def get_yearly_energy_stats(self, station_id: str, date: str) -> dict[str, Any]:
        """Get yearly energy statistics (buy/sell/charge/discharge) for a power station.
        
        Uses GetChartByPlant with chartIndexId=7 and Range=4 to get yearly totals.
        The year is determined by the provided date.
        """
        if not self._token_data:
            await self.authenticate()
        
        # Import here to get the endpoint constant
        from .const import GET_CHART_BY_PLANT_ENDPOINT
        
        result = await self._request(
            GET_CHART_BY_PLANT_ENDPOINT,
            data={
                "Id": station_id,
                "Date": date,
                "Range": "4",  # Year
                "ChartIndexId": "7",  # Energy statistics
                "IsDetailFull": False,
            },
        )
        
        return result.get("data", {})

    async def get_all_time_energy_stats(self, station_id: str, date: str) -> dict[str, Any]:
        """Get all-time energy statistics (buy/sell/charge/discharge) for a power station.
        
        Uses GetChartByPlant with chartIndexId=7 and Range=1 to get all-time totals.
        """
        if not self._token_data:
            await self.authenticate()
        
        # Import here to get the endpoint constant
        from .const import GET_CHART_BY_PLANT_ENDPOINT
        
        result = await self._request(
            GET_CHART_BY_PLANT_ENDPOINT,
            data={
                "Id": station_id,
                "Date": date,
                "Range": "1",  # All time
                "ChartIndexId": "7",  # Energy statistics
                "IsDetailFull": False,
            },
        )
        
        return result.get("data", {})

    async def get_all_station_data(self) -> dict[str, dict[str, Any]]:
        """Get all data for all power stations."""
        from datetime import datetime
        
        stations = await self.get_power_stations()
        all_data = {}
        
        for station in stations:
            station_id = station.get("id") if isinstance(station, dict) else station
            if not station_id:
                continue
                
            try:
                # Get plant details first - it contains local_date in the plant's timezone
                plant_details = await self.get_plant_details(station_id)
                
                # Extract the date from the plant's local_date (format: "YYYY-MM-DD HH:MM:SS")
                # This ensures we use the correct date in the plant's timezone, not the HA server's timezone
                info = plant_details.get("info", {})
                local_date_str = info.get("local_date", "")
                if local_date_str:
                    # Parse date portion from "YYYY-MM-DD HH:MM:SS"
                    plant_date = local_date_str.split(" ")[0]
                else:
                    # Fallback to server time if local_date not available
                    _LOGGER.warning("No local_date in plant details for station %s, using server time", station_id)
                    plant_date = datetime.now().strftime("%Y-%m-%d")
                
                powerflow = await self.get_powerflow(station_id)
                daily_energy_stats = await self.get_daily_energy_stats(station_id, plant_date)
                monthly_energy_stats = await self.get_monthly_energy_stats(station_id, plant_date)
                yearly_energy_stats = await self.get_yearly_energy_stats(station_id, plant_date)
                all_time_energy_stats = await self.get_all_time_energy_stats(station_id, plant_date)
                
                all_data[station_id] = {
                    "station_id": station_id,
                    "details": plant_details,
                    "powerflow": powerflow,
                    "energy_stats": daily_energy_stats,  # Keep key name for backward compatibility
                    "monthly_energy_stats": monthly_energy_stats,
                    "yearly_energy_stats": yearly_energy_stats,
                    "all_time_energy_stats": all_time_energy_stats,
                }
            except LGESApiError as err:
                _LOGGER.error("Failed to get data for station %s: %s", station_id, err)
                
        return all_data

