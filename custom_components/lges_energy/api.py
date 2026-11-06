"""API client for LG Energy Solutions systems (SEMS+ / Solarportal+).

GoodWe, who ran the old LG RESU Home Monitor backend, retired that SEMS portal
API in 2026. LG systems are now monitored through Solarportal+, an unbranded
edition of GoodWe's SEMS+ platform (not run by LG). This client talks to the
SEMS+ web API and returns one dictionary per station, ready for the sensors:

    info       station details (capacities, rated power, model), status and last update time
    power      live power in W (battery + = discharging, grid + = importing)
    energy     kWh totals for today / month / year / all_time
    rates      self-consumption and self-sufficiency % for today
    income     currency, today, export_today and total
    inverter   inverter temperature, grid voltage, backup power (W) and
               per-string solar power (W) and voltage under "strings"
    batteries  battery units reported by storage inverters
    alarms     recent alarms, newest first (None if they couldn't be fetched)
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .const import (
    ALARM_LOOKBACK_DAYS,
    ALARM_PATH,
    AUTH_EXPIRED_CODES,
    DEFAULT_GATEWAY,
    DEVICE_STATUS_PATH,
    EARLIEST_STATS_YEAR,
    LOGIN_HOSTS,
    PRODUCTION_PATH,
    RATE_LIMIT_CODE,
    RELATED_DEVICES_PATH,
    STATION_FLOW_PATH,
    STATION_DETAILS_PATH,
    STATION_LIST_PATH,
    STATISTICS_ITEM_MAP,
    STATISTICS_PATH,
    STATISTICS_RATE_MAP,
    STATISTICS_SUMMARY_MAP,
    STORAGE_DEVICE_TYPES,
    SUCCESS_CODES,
    TELEMETRY_MAP,
    TELEMETRY_PATH,
)

_LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_EMPTY_TOKEN = {
    "uid": "",
    "timestamp": 0,
    "token": "",
    "client": "semsPlusWeb",
    "version": "",
    "language": "en",
}
_DEVICE_CACHE_SECONDS = 3600
_PAST_YEAR_CACHE_SECONDS = 86400
_INCOME_RETRY_SECONDS = 6 * 3600
_READINGS_RETRY_SECONDS = 3600
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class LGESApiError(Exception):
    """Exception for LGES API errors."""


class LGESAuthError(LGESApiError):
    """Exception for authentication errors."""


class LGESTemporaryError(LGESApiError):
    """A network failure or rate limit; worth retrying on the next update."""


class _HTTPUnauthorized(LGESTemporaryError):
    """The server answered HTTP 401/403, e.g. because the session expired."""


def _to_float(value: Any) -> float | None:
    """Return value as a finite float, or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _response_message(result: dict[str, Any]) -> str:
    """Return the most useful error text from an API response."""
    for key in ("description", "errorMsg", "msg", "translationCode"):
        if isinstance(result.get(key), str) and result[key]:
            return result[key]
    return "Unknown error"


def _sum_points(entry: Any) -> float | None:
    """Add up the values in a dataList entry's statisticsList."""
    values = [
        number
        for point in (entry.get("statisticsList") or [] if isinstance(entry, dict) else [])
        if isinstance(point, dict) and (number := _to_float(point.get("val"))) is not None
    ]
    return sum(values) if values else None


def _year_range(year: int) -> tuple[datetime, datetime]:
    """Return the first and last second of a year."""
    return datetime(year, 1, 1), datetime(year, 12, 31, 23, 59, 59)


def _watts(kw: float | None) -> float | None:
    """Convert kW to W."""
    return None if kw is None else round(kw * 1000, 1)


def parse_statistics(data: Any) -> dict[str, float]:
    """Convert a statistics response into energy totals (kWh)."""
    if not isinstance(data, dict):
        return {}

    totals: dict[str, float] = {}
    for entry in data.get("dataList") or []:
        if not isinstance(entry, dict):
            continue
        item = entry.get("item")
        if item in STATISTICS_ITEM_MAP and (total := _sum_points(entry)) is not None:
            totals[item] = total

    # Fall back to the summary fields for anything the item list left out.
    for summary_key, item in STATISTICS_SUMMARY_MAP.items():
        if item not in totals and (number := _to_float(data.get(summary_key))) is not None:
            totals[item] = number

    return {STATISTICS_ITEM_MAP[item]: round(value, 3) for item, value in totals.items()}


def parse_rates(data: Any) -> dict[str, float]:
    """Return the self-consumption and self-sufficiency percentages."""
    if not isinstance(data, dict):
        return {}
    return {
        name: round(number, 2)
        for key, name in STATISTICS_RATE_MAP.items()
        if (number := _to_float(data.get(key))) is not None
    }


def parse_alarms(data: Any) -> list[dict[str, Any]]:
    """Convert an alarm page into a newest-first list of simple alarm records."""
    if not isinstance(data, dict):
        return []
    alarms: list[dict[str, Any]] = []
    for item in data.get("dataList") or []:
        if not isinstance(item, dict):
            continue
        level = item.get("alarmLevel")
        alarms.append(
            {
                "name": item.get("warningNameEn") or item.get("warningname"),
                "device": item.get("deviceName"),
                "level": level.rsplit("_", 1)[-1].lower() if isinstance(level, str) else None,
                "started": item.get("happentimes"),
                "cleared": item.get("recoverytimes") or None,
                # Status 0 = still happening, 1 = recovered.
                "active": _to_float(item.get("status")) == 0,
            }
        )
    alarms.sort(key=lambda alarm: str(alarm["started"] or ""), reverse=True)
    return alarms


def parse_flow(flow: Any) -> dict[str, float]:
    """Convert a station flow response into live power (W) and battery level.

    SEMS+ reports signed kW: pBat is + discharging / - charging, and pGrid is
    + exporting / - importing. Grid is flipped here so + means importing.
    """
    if not isinstance(flow, dict):
        return {}

    solar = _to_float(flow.get("pSystem"))
    if solar is None:
        solar = _to_float(flow.get("pAc"))
    load = _to_float(flow.get("pConsum"))
    grid = _to_float(flow.get("pGrid"))

    power = {
        "solar": _watts(abs(solar)) if solar is not None else None,
        "load": _watts(abs(load)) if load is not None else None,
        "battery": _watts(_to_float(flow.get("pBat"))),
        "grid": _watts(-grid) if grid is not None else None,
        "battery_soc": _to_float(flow.get("soc")),
    }
    # Avoid reporting -0.0.
    return {key: value + 0.0 for key, value in power.items() if value is not None}


def parse_telemetry(data: Any) -> dict[str, Any]:
    """Pull the readings we use out of an inverter telemetry response.

    The response is a list of groups, each with "factors" such as
    {"code": "Vac", "data": "235", "unit": "V"}. Solar strings appear as
    "MPPT-1:Ppv" (power) and "MPPT-1:Vpv" (voltage), one pair per string.
    """
    readings: dict[str, Any] = {}
    strings: dict[int, dict[str, float]] = {}
    for group in data if isinstance(data, list) else []:
        factors = group.get("factors") if isinstance(group, dict) else None
        for factor in factors or []:
            if not isinstance(factor, dict) or not isinstance(factor.get("code"), str):
                continue
            code = factor["code"]
            string = re.fullmatch(r"MPPT-(\d+):(Ppv|Vpv)", code)
            if code not in TELEMETRY_MAP and not string:
                continue
            value = _to_float(factor.get("data"))
            if value is None:
                continue
            if str(factor.get("unit") or "").lower() == "kw":
                value *= 1000
            value = round(value, 1) + 0.0
            if string:
                measure = "power" if string.group(2) == "Ppv" else "voltage"
                strings.setdefault(int(string.group(1)), {})[measure] = value
            else:
                readings[TELEMETRY_MAP[code]] = value
    if strings:
        readings["strings"] = dict(sorted(strings.items()))
    return readings


def parse_station_details(data: Any) -> dict[str, float]:
    """Pull the capacities out of a station details ("Basic Information") response.

    The portal shows baseInfo.batteryCapacity in kWh, baseInfo.capacity
    (solar panels) in kWp and baseInfo.installedPower (inverter) in kW.
    """
    if not isinstance(data, dict):
        return {}
    base = data.get("baseInfo") if isinstance(data.get("baseInfo"), dict) else data
    fields = {
        "battery_capacity": "batteryCapacity",
        "solar_capacity": "capacity",
        "rated_power": "installedPower",
    }
    details = {}
    for name, key in fields.items():
        value = _to_float(base.get(key))
        # 0 means "not entered" in the portal.
        if value:
            details[name] = value
    return details


def parse_devices(data: Any) -> list[dict[str, Any]]:
    """Flatten an all-status response into a list of devices."""
    devices: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        return devices
    for group in data.get("deviceDetailList") or []:
        if not isinstance(group, dict):
            continue
        device_type = group.get("deviceType")
        for status_group in group.get("statusDetailList") or []:
            if not isinstance(status_group, dict):
                continue
            detail_map = status_group.get("detailMap") or {}
            for sn in status_group.get("snList") or []:
                detail = detail_map.get(sn) if isinstance(detail_map, dict) else None
                devices.append(
                    {
                        "sn": sn,
                        "deviceType": device_type,
                        "status": status_group.get("status"),
                        **(detail if isinstance(detail, dict) else {}),
                    }
                )
    return devices


def parse_income(production: Any) -> float | None:
    """Pull the income figure out of a production response.

    SEMS+ returns flat totals, e.g. {"profitProStats": 0.71, "currency": "AUD"}.
    profitProStats is income on all generation (what the portal shows as
    income); profitGridStats is the export-only part.
    """
    if not isinstance(production, dict):
        return None
    for key in ("profitProStats", "profitGridStats"):
        if (number := _to_float(production.get(key))) is not None:
            return round(number, 4)
    return None


def station_zone(station: dict[str, Any]) -> tzinfo | None:
    """Return the station's time zone (an IANA name or "UTC+10:00" style)."""
    name = station.get("timeZone")
    if not isinstance(name, str) or not name:
        return None
    offset = re.fullmatch(r"(?:UTC|GMT)\s*([+-])(\d{1,2})(?::?(\d{2}))?", name.strip())
    if offset:
        sign = -1 if offset.group(1) == "-" else 1
        delta = timedelta(hours=int(offset.group(2)), minutes=int(offset.group(3) or 0))
        return timezone(sign * delta)
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        _LOGGER.debug("Unknown station time zone %s", name)
    return None


def install_year(
    devices: list[dict[str, Any]], station: dict[str, Any], current_year: int
) -> int:
    """Best guess at the year the system was installed."""
    years: list[int] = []
    for value in [d.get("addTime") for d in devices] + [station.get("createTime")]:
        number = _to_float(value)
        if number is not None and number > 1e11:  # epoch milliseconds
            try:
                years.append(datetime.fromtimestamp(number / 1000).year)
            except (OverflowError, OSError, ValueError):
                continue
        elif isinstance(value, str) and re.match(r"^\d{4}-", value):
            years.append(int(value[:4]))
    valid = [y for y in years if EARLIEST_STATS_YEAR <= y <= current_year]
    return min(valid) if valid else EARLIEST_STATS_YEAR


def _is_storage(device: dict[str, Any]) -> bool:
    """Return True for devices that can have batteries attached."""
    if device.get("deviceType") not in STORAGE_DEVICE_TYPES:
        return False
    # Inverters only count if they're hybrid ("store") models.
    return device.get("deviceType") != "INVERTER" or device.get("subtype") in (None, "store")


def _first_inverter(devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the station's first inverter that has a serial number."""
    return next(
        (
            d
            for d in devices
            if d.get("deviceType") == "INVERTER" and isinstance(d.get("sn"), str)
        ),
        None,
    )


class LGESApiClient:
    """API client for the SEMS+ / Solarportal+ web API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self._token_data: dict[str, Any] | None = None
        self._gateway = DEFAULT_GATEWAY
        self._neutral = LOGIN_HOSTS[0][1]
        self._cache: dict[str, tuple[float, Any]] = {}

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _hash_password(password: str) -> str:
        """SEMS+ expects base64(md5_hex(password))."""
        digest = hashlib.md5(password.encode("utf-8"), usedforsecurity=False).hexdigest()
        return base64.b64encode(digest.encode("utf-8")).decode("utf-8")

    @staticmethod
    def _signature(token_data: dict[str, Any]) -> str:
        """Build the X-Signature header the web portal sends with every call."""
        epoch_ms = round(time.time() * 1000)
        digest = hashlib.sha256(
            f"{epoch_ms}@{token_data.get('uid', '')}@{token_data.get('token', '')}".encode()
        ).hexdigest()
        return base64.b64encode(f"{digest}@{epoch_ms}".encode()).decode()

    def _headers(self, token_data: dict[str, Any], neutral: str) -> dict[str, str]:
        token = json.dumps(token_data, separators=(",", ":"))
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "token": token,
            "X-Signature": self._signature(token_data),
            "neutral": neutral,
            "currentLang": "en",
            "User-Agent": _USER_AGENT,
        }

    @staticmethod
    def _gateway_from_login(data: dict[str, Any]) -> str:
        """Return the regional gateway origin from a login response."""
        api = data.get("api")
        if isinstance(api, str):
            match = re.match(r"^(https?://[^/]+)", api)
            if match:
                return match.group(1)
        region = data.get("region")
        if isinstance(region, str) and re.fullmatch(r"[a-z]{2}", region):
            return f"https://{region}-gateway.semsportal.com"
        return DEFAULT_GATEWAY

    def _cache_get(self, key: str, max_age: float) -> Any | None:
        entry = self._cache.get(key)
        if entry and time.monotonic() - entry[0] < max_age:
            return entry[1]
        return None

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = (time.monotonic(), value)

    def _failed_recently(self, key: str, seconds: float) -> bool:
        """Return True if the request named key was refused in the last seconds."""
        return self._cache_get(f"failed:{key}", seconds) is not None

    async def _send(
        self,
        method: str,
        url: str,
        *,
        token_data: dict[str, Any],
        neutral: str,
        json_body: Any = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send one HTTP request and return the decoded JSON body."""
        try:
            async with self._session.request(
                method,
                url,
                json=json_body,
                params=params,
                headers=self._headers(token_data, neutral),
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                if response.status == 429:
                    raise LGESTemporaryError("Rate limited by the SEMS+ API")
                if response.status in (401, 403):
                    raise _HTTPUnauthorized(f"Request to {url} refused (HTTP {response.status})")
                response.raise_for_status()
                result = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LGESTemporaryError(f"Request to {url} failed: {err}") from err

        if not isinstance(result, dict):
            raise LGESApiError(f"Unexpected response from {url}")
        return result

    # ------------------------------------------------------------- auth / calls

    async def authenticate(self) -> None:
        """Sign in, trying Solarportal+ first and then GoodWe's own SEMS+ host."""
        body = {
            "account": self._username,
            "pwd": self._hash_password(self._password),
            "agreement": 1,
            "isLocal": False,
            "isChinese": False,
        }
        last_error = "no login host responded"
        rejected = False
        unreachable = False

        for url, neutral in LOGIN_HOSTS:
            try:
                result = await self._send(
                    "POST", url, token_data=_EMPTY_TOKEN, neutral=neutral, json_body=body
                )
            except LGESApiError as err:
                _LOGGER.debug("Login via %s failed: %s", url, err)
                last_error = str(err)
                unreachable = True
                continue

            code = result.get("code")
            data = result.get("data")
            if code == RATE_LIMIT_CODE:
                self._token_data = None
                raise LGESTemporaryError("Sign-in rate limited by the SEMS+ API")
            if code not in SUCCESS_CODES or not isinstance(data, dict):
                rejected = True
                last_error = f"{_response_message(result)} (code {code})"
                _LOGGER.debug("Login via %s rejected: %s", url, last_error)
                continue

            if data.get("mfaRequired"):
                raise LGESAuthError(
                    "This account has two-factor sign-in enabled, which the "
                    "integration can't complete. Turn it off in the LG portal."
                )
            if not data.get("token"):
                last_error = "login response had no token"
                continue

            self._token_data = data
            self._neutral = neutral
            self._gateway = self._gateway_from_login(data)
            _LOGGER.debug("Signed in via %s; data gateway %s", url, self._gateway)
            return

        self._token_data = None
        # Only blame the login if every host answered: if one was down, it may
        # be the one that would have accepted it.
        if rejected and not unreachable:
            raise LGESAuthError(f"Authentication failed: {last_error}")
        raise LGESTemporaryError(f"Could not sign in: {last_error}")

    async def _call(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: dict[str, str] | None = None,
        retry_auth: bool = True,
    ) -> Any:
        """Call a data endpoint and return its "data" field, signing in if needed."""
        if not self._token_data:
            await self.authenticate()
        assert self._token_data is not None

        try:
            result = await self._send(
                method,
                f"{self._gateway}{path}",
                token_data=self._token_data,
                neutral=self._neutral,
                json_body=json_body,
                params=params,
            )
        except _HTTPUnauthorized as err:
            expired_reason = str(err)
            result = {}
        else:
            expired_reason = (
                f"{_response_message(result)} (code {result.get('code')})"
                if result.get("code") in AUTH_EXPIRED_CODES
                else None
            )

        code = result.get("code")
        if expired_reason is None and code in SUCCESS_CODES:
            _LOGGER.debug("%s %s -> %s", method, path, result.get("data"))
            return result.get("data")

        if expired_reason is not None:
            self._token_data = None
            if retry_auth:
                _LOGGER.debug("Session expired (%s); signing in again", expired_reason)
                return await self._call(
                    method, path, json_body=json_body, params=params, retry_auth=False
                )
            # The login itself worked, so this isn't a password problem.
            raise LGESTemporaryError(
                f"{path}: session rejected straight after signing in: {expired_reason}"
            )

        if code == RATE_LIMIT_CODE:
            raise LGESTemporaryError("Rate limited by the SEMS+ API")
        raise LGESApiError(f"{path}: {_response_message(result)} (code {code})")

    # ---------------------------------------------------------------- endpoints

    async def get_power_stations(self) -> list[dict[str, Any]]:
        """Get the stations visible to this account."""
        data = await self._call(
            "POST", STATION_LIST_PATH, json_body={"current": 1, "size": 100}
        )
        stations = data.get("dataList") if isinstance(data, dict) else None
        return [
            station
            for station in stations or []
            if isinstance(station, dict) and isinstance(station.get("id"), str)
        ]

    async def get_station_flow(self, station_id: str) -> dict[str, Any]:
        """Get live power flow (kW) for a station."""
        data = await self._call("GET", STATION_FLOW_PATH, params={"stationId": station_id})
        return data if isinstance(data, dict) else {}

    async def get_devices(self, station_id: str) -> list[dict[str, Any]]:
        """Get the station's devices (cached for an hour)."""
        key = f"devices:{station_id}"
        cached = self._cache_get(key, _DEVICE_CACHE_SECONDS)
        if cached is not None:
            return cached
        data = await self._call("GET", DEVICE_STATUS_PATH, params={"stationId": station_id})
        devices = parse_devices(data)
        self._cache_set(key, devices)
        return devices

    async def get_batteries(
        self, station_id: str, devices: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Get the battery units attached to the station's storage inverters."""
        batteries: list[dict[str, Any]] = []
        for device in filter(_is_storage, devices):
            sn = device.get("sn")
            if not isinstance(sn, str):
                continue
            related = await self._call(
                "GET",
                RELATED_DEVICES_PATH.format(sn=sn),
                params={
                    "sn": sn,
                    "deviceType": "ENERGY_STORAGE_INTEGRATED_CABINET",
                    "pwId": station_id,
                },
            )
            for unit in related if isinstance(related, list) else []:
                if not isinstance(unit, dict):
                    continue
                if (unit.get("type") or unit.get("deviceType")) != "BAT_SYS":
                    continue
                batteries.append(
                    {
                        "name": unit.get("sn") or unit.get("name") or "battery",
                        "soc": _to_float(unit.get("soc")),
                        "status": unit.get("status"),
                        "connected": unit.get("isConnected"),
                    }
                )
        return batteries

    async def get_statistics_data(
        self, station_id: str, dimension: str, start: datetime, end: datetime
    ) -> Any:
        """Get the raw statistics response data for a period."""
        return await self._call(
            "POST",
            STATISTICS_PATH,
            json_body={
                "stationId": station_id,
                "isReport": False,
                "items": list(STATISTICS_ITEM_MAP),
                "dimension": dimension,
                "startTime": start.strftime(_TIME_FORMAT),
                "endTime": end.strftime(_TIME_FORMAT),
            },
        )

    async def get_statistics(
        self, station_id: str, dimension: str, start: datetime, end: datetime
    ) -> dict[str, float]:
        """Get energy totals (kWh) for a period."""
        return parse_statistics(
            await self.get_statistics_data(station_id, dimension, start, end)
        )

    async def get_production(
        self, station_id: str, start: datetime, end: datetime, dimension: str = "day"
    ) -> dict[str, Any]:
        """Get production and income figures (flat totals) for a period."""
        data = await self._call(
            "POST",
            PRODUCTION_PATH,
            json_body={
                "stationId": station_id,
                "items": ["profitProStats", "profitGridStats", "proSystemTotalStats"],
                "dimension": dimension,
                "isReport": False,
                "startTime": start.strftime(_TIME_FORMAT),
                "endTime": end.strftime(_TIME_FORMAT),
            },
        )
        return data if isinstance(data, dict) else {}

    async def get_alarms(
        self, station_id: str, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        """Get the station's alarms that started in a period (newest first)."""
        data = await self._call(
            "POST",
            ALARM_PATH,
            json_body={
                "stationId": station_id,
                "startTime": start.strftime(_TIME_FORMAT),
                "endTime": end.strftime(_TIME_FORMAT),
                "timeType": 1,  # filter on when the alarm started
                "pageIndex": 1,
                "pageSize": 100,
            },
        )
        return parse_alarms(data)

    async def get_station_details(self, station_id: str) -> dict[str, float]:
        """Get battery capacity, solar capacity and rated power (cached for an hour).

        These are settings that rarely change. If the request is refused it
        isn't tried again for an hour; network errors retry next update.
        """
        key = f"details:{station_id}"
        cached = self._cache_get(key, _DEVICE_CACHE_SECONDS)
        if cached is not None:
            return cached
        if self._failed_recently(key, _DEVICE_CACHE_SECONDS):
            return {}
        data = await self._optional(
            "station details",
            self._call("GET", STATION_DETAILS_PATH.format(station_id=station_id)),
            None,
            backoff_key=key,
        )
        if data is None:
            return {}
        details = parse_station_details(data)
        self._cache_set(key, details)
        return details

    async def get_inverter_readings(
        self, station_id: str, devices: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Get temperature, grid voltage, backup power and solar strings from the first inverter.

        Some accounts reject this request, so if it's refused it isn't tried
        again for an hour; network errors retry next update.
        """
        inverter = _first_inverter(devices)
        if inverter is None:
            return {}
        key = f"readings:{inverter['sn']}"
        if self._failed_recently(key, _READINGS_RETRY_SECONDS):
            return {}
        data = await self._optional(
            "inverter readings",
            self._call(
                "GET",
                TELEMETRY_PATH.format(sn=inverter["sn"]),
                params={"deviceType": "INVERTER", "pwId": station_id},
            ),
            None,
            backoff_key=key,
        )
        return parse_telemetry(data)

    # ------------------------------------------------------------ data assembly

    async def _optional(
        self, label: str, coro: Any, default: Any, *, backoff_key: str | None = None
    ) -> Any:
        """Await an optional request; log and return default if it fails.

        With a backoff_key, a refused request (not a network error or rate
        limit) is remembered so the caller can skip it for a while.
        """
        try:
            return await coro
        except LGESAuthError:
            raise
        except LGESTemporaryError as err:
            _LOGGER.warning("Could not fetch %s: %s", label, err)
        except LGESApiError as err:
            if backoff_key is None:
                _LOGGER.warning("Could not fetch %s: %s", label, err)
            else:
                _LOGGER.warning("Could not fetch %s (trying again later): %s", label, err)
                self._cache_set(f"failed:{backoff_key}", True)
        return default

    async def _all_time_totals(
        self, station_id: str, first_year: int, this_year: dict[str, float], year: int
    ) -> dict[str, float]:
        """Lifetime totals = completed years (cached daily) + this year so far.

        SEMS+ rejects a "total" dimension and returns zeros for multi-year
        ranges, so each year is requested on its own. If any year is missing
        the lifetime figures are left out rather than reported too low.
        This year's figures already include today.
        """
        totals: dict[str, float] = dict(this_year)
        if not totals:
            return {}
        for past in range(first_year, year):
            key = f"year:{station_id}:{past}"
            stats = self._cache_get(key, _PAST_YEAR_CACHE_SECONDS)
            if stats is None:
                stats = await self._optional(
                    f"{past} totals",
                    self.get_statistics(station_id, "year", *_year_range(past)),
                    None,
                )
                if stats is None:
                    return {}
                self._cache_set(key, stats)
            for field, value in stats.items():
                totals[field] = totals.get(field, 0.0) + value
        return {field: round(value, 3) for field, value in totals.items()}

    async def _total_income(
        self, station_id: str, first_year: int, year: int
    ) -> float | None:
        """Lifetime income = each year's income added up (past years cached daily).

        If this year has no income figure, the account doesn't report yearly
        income, so it isn't asked again for 6 hours. Past years with no figure
        count as 0: they're usually from before the system was installed.
        """
        key = f"income:{station_id}"
        if self._failed_recently(key, _INCOME_RETRY_SECONDS):
            return None

        async def fetch(each: int) -> Any:
            # None if the request failed (refusals back off; network errors retry).
            return await self._optional(
                f"{each} income",
                self.get_production(station_id, *_year_range(each), dimension="year"),
                None,
                backoff_key=key,
            )

        production = await fetch(year)
        if production is None:
            return None
        total = parse_income(production)
        if total is None:
            _LOGGER.warning("Yearly income not available (trying again in 6 hours)")
            self._cache_set(f"failed:{key}", True)
            return None

        for past in range(first_year, year):
            past_key = f"{key}:{past}"
            income = self._cache_get(past_key, _PAST_YEAR_CACHE_SECONDS)
            if income is None:
                production = await fetch(past)
                if production is None:
                    return None
                income = parse_income(production) or 0.0
                self._cache_set(past_key, income)
            total += income
        return round(total, 2)

    async def _station_data(self, station: dict[str, Any]) -> dict[str, Any]:
        station_id = station["id"]
        zone = station_zone(station)
        now = datetime.now(zone) if zone else datetime.now().astimezone()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        today_end = today + timedelta(days=1) - timedelta(seconds=1)

        flow = await self.get_station_flow(station_id)
        devices = await self._optional("device list", self.get_devices(station_id), [])
        batteries = await self._optional(
            "battery details", self.get_batteries(station_id, devices), []
        )
        details = await self.get_station_details(station_id)
        readings = await self.get_inverter_readings(station_id, devices)
        today_data = await self._optional(
            "today's totals",
            self.get_statistics_data(station_id, "day", today, today_end),
            None,
        )
        month = await self._optional(
            "this month's totals",
            self.get_statistics(station_id, "day", today.replace(day=1), today_end),
            {},
        )
        this_year = await self._optional(
            "this year's totals",
            self.get_statistics(station_id, "year", *_year_range(today.year)),
            {},
        )
        first_year = install_year(devices, station, today.year)
        all_time = await self._all_time_totals(station_id, first_year, this_year, today.year)
        production = await self._optional(
            "income", self.get_production(station_id, today, today_end), {}
        )
        total_income = await self._total_income(station_id, first_year, today.year)
        alarms = await self._optional(
            "alarms",
            self.get_alarms(
                station_id, today - timedelta(days=ALARM_LOOKBACK_DAYS), today_end
            ),
            None,
        )

        status = _to_float(flow.get("status"))
        if status is None:
            status = _to_float(station.get("status"))

        last_update = None
        refresh = flow.get("refreshTime")
        if isinstance(refresh, str) and refresh:
            try:
                last_update = datetime.fromisoformat(refresh)
                if last_update.tzinfo is None:
                    # No zone given: it's the station's local time.
                    last_update = last_update.replace(tzinfo=zone or now.tzinfo)
            except ValueError:
                _LOGGER.debug("Could not parse refreshTime %s", refresh)

        today_income = parse_income(production)
        export_income = _to_float(production.get("profitGridStats"))
        inverter = _first_inverter(devices)
        return {
            "info": {
                "name": station.get("name"),
                "address": station.get("googleAddress") or station.get("address"),
                "model": (inverter or {}).get("model") or None,
                "capacity": details.get("solar_capacity")
                or _to_float(station.get("pvInstallP")),
                "rated_power": details.get("rated_power")
                or _to_float(station.get("installedPower")),
                "battery_capacity": details.get("battery_capacity"),
                "status": int(status) if status is not None else None,
                "last_update": last_update,
            },
            "power": parse_flow(flow),
            "energy": {
                "today": parse_statistics(today_data),
                "month": month,
                "year": this_year,
                "all_time": all_time,
            },
            "rates": parse_rates(today_data),
            "income": {
                "currency": production.get("currency")
                if isinstance(production.get("currency"), str)
                else None,
                "today": round(today_income, 2) if today_income is not None else None,
                # profitGridStats: the part of today's income from exported energy.
                "export_today": round(export_income, 2) if export_income is not None else None,
                "total": total_income,
            },
            "inverter": readings,
            "batteries": batteries,
            "alarms": alarms,
        }

    async def get_all_station_data(self) -> dict[str, dict[str, Any]]:
        """Get all data for all power stations, keyed by station ID."""
        all_data: dict[str, dict[str, Any]] = {}
        for station in await self.get_power_stations():
            try:
                all_data[station["id"]] = await self._station_data(station)
            except LGESAuthError:
                raise
            except LGESApiError as err:
                _LOGGER.error("Failed to get data for station %s: %s", station["id"], err)
        return all_data
