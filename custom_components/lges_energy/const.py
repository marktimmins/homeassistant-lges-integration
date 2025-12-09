"""Constants for the LG Energy Solutions integration."""

DOMAIN = "lges_energy"

# API Endpoints
DEFAULT_API_BASE = "https://au.semsportal.com/api/"
LOGIN_ENDPOINT = "v2/common/crosslogin"
GET_STATIONS_ENDPOINT = "PowerStation/GetPowerStationIdByOwner"
GET_PLANT_DETAIL_ENDPOINT = "v3/PowerStation/GetPlantDetailByPowerstationId"
GET_POWERFLOW_ENDPOINT = "v2/PowerStation/GetPowerflow"
GET_CHART_ENDPOINT = "v2/Charts/GetPlantPowerChart"
GET_CHART_BY_PLANT_ENDPOINT = "v2/Charts/GetChartByPlant"

# Token structure for unauthenticated requests
EMPTY_TOKEN_DATA = {
    "uid": "",
    "timestamp": 0,
    "token": "",
    "client": "web",
    "version": "",
    "language": "en"
}

# Configuration keys
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"

# Sensor types
SENSOR_TYPE_POWER = "power"
SENSOR_TYPE_ENERGY = "energy"
SENSOR_TYPE_BATTERY = "battery"
SENSOR_TYPE_VOLTAGE = "voltage"
SENSOR_TYPE_CURRENT = "current"
