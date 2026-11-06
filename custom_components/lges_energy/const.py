"""Constants for the LG Energy Solutions integration."""

DOMAIN = "lges_energy"

# --- SEMS+ / Solarportal+ API -------------------------------------------------
# GoodWe retired the old SEMS portal API in 2026. LG accounts now sign in via
# Solarportal+ (an unbranded edition of SEMS+, not run by LG); GoodWe's own
# SEMS+ host is kept as a fallback. Both return a token plus a regional gateway ("api") that all
# data requests go to.
LOGIN_HOSTS: list[tuple[str, str]] = [
    # (login URL, value of the "neutral" header)
    ("https://au.solarportalplus.com/web/sems/sems-user/api/v1/auth/cross-login", "1"),
    ("https://semsplus.goodwe.com/web/sems/sems-user/api/v1/auth/cross-login", "0"),
]
DEFAULT_GATEWAY = "https://au-gateway.semsportal.com"

STATION_LIST_PATH = "/web/sems/sems-plant/api/portal/stations/page"
STATION_FLOW_PATH = "/web/sems/sems-plant/api/stations/flow"
DEVICE_STATUS_PATH = "/web/sems/sems-plant/api/stations/device/all-status"
RELATED_DEVICES_PATH = "/web/sems/sems-plant/api/equipments/{sn}/relatedDevices"
TELEMETRY_PATH = "/web/sems/sems-plant/api/equipments/{sn}/telemetry"
# Station settings, as shown on the portal's "Basic Information" tab.
STATION_DETAILS_PATH = "/web/sems/sems-plant/api/stations/{station_id}"
STATISTICS_PATH = "/web/sems/sems-plant/api/stations/statistics"
PRODUCTION_PATH = "/web/sems/sems-plant/api/stations/production"
ALARM_PATH = "/web/sems/sems-alarm/api/v2/alarm/page"
# How far back to look for alarms (the portal's default view is 90 days).
ALARM_LOOKBACK_DAYS = 90

# Statistics items and the energy keys the sensors read.
STATISTICS_ITEM_MAP = {
    "proSystemTotalStats": "generation",
    "proPurchaseStats": "grid_import",
    "proGridStats": "grid_export",
    "proSelfConsumStats": "self_use",
    "proConsumStats": "consumption",
    "proCharStats": "battery_charge",
    "proDischarStats": "battery_discharge",
}
# Summary fields some responses carry instead of (or as well as) the item list.
STATISTICS_SUMMARY_MAP = {
    "production": "proSystemTotalStats",
    "proPurchase": "proPurchaseStats",
    "proGrid": "proGridStats",
    "proSelfConsum": "proSelfConsumStats",
    "proConsum": "proConsumStats",
    "proChar": "proCharStats",
    "proDischar": "proDischarStats",
}
# Inverter readings (telemetry factor codes) and the keys the sensors read.
TELEMETRY_MAP = {
    "Temperature": "temperature",  # degrees C
    "Vac": "grid_voltage",  # V
    "pBackup": "backup_power",  # kW, converted to W
}

# Percentages in the statistics summary.
STATISTICS_RATE_MAP = {
    "proSelfConsumRate": "self_consumption_rate",  # share of solar used at home
    "contributionRate": "self_sufficiency",  # share of home use met by solar/battery
}

SUCCESS_CODES = {"00000", "0", 0}
# Codes meaning the session token is no longer accepted.
AUTH_EXPIRED_CODES = {"100002", "C0602", "C0607", 100002}
RATE_LIMIT_CODE = "GY0429"

# Device types (from all-status) that can have batteries attached.
STORAGE_DEVICE_TYPES = {"INVERTER", "ENERGY_STORAGE_INTEGRATED_CABINET"}

# Earliest year to look back to when the install year is unknown.
EARLIEST_STATS_YEAR = 2015

