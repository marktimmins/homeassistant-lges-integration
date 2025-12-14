"""Sensor platform for LG Energy Solutions."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LGESDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LG Energy Solutions sensors based on a config entry."""
    coordinator: LGESDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities: list[LGESSensor] = []
    
    for station_id, station_data in coordinator.data.items():
        # Get station info for device registration
        details = station_data.get("details", {})
        info = details.get("info", {})
        
        # Use address for device name (more useful for home users), fallback to station name
        station_name = (
            info.get("address") 
            or info.get("stationname") 
            or f"LGES Station {station_id[:8]}"
        )
        
        # Create device info
        device_info = DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            name=station_name,
            manufacturer="LG Energy Solutions",
            model=info.get("powerstation_type", "Solar Inverter System"),
            entry_type=DeviceEntryType.SERVICE,
        )
        
        # Add all sensors for this station
        entities.extend([
            # Real-time power flow sensors (from powerflow object)
            LGESSolarPowerSensor(coordinator, station_id, device_info),
            LGESBatteryPowerSensor(coordinator, station_id, device_info),
            LGESLoadPowerSensor(coordinator, station_id, device_info),
            LGESGridPowerSensor(coordinator, station_id, device_info),
            
            # Battery sensors
            LGESBatterySOCSensor(coordinator, station_id, device_info),
            LGESBatteryCapacitySensor(coordinator, station_id, device_info),
            
            # Energy stats from GetChartByPlant (daily totals) - Range=2
            LGESDailyGenerationSensor(coordinator, station_id, device_info),
            LGESGridImportSensor(coordinator, station_id, device_info),
            LGESGridExportSensor(coordinator, station_id, device_info),
            LGESSelfUseSensor(coordinator, station_id, device_info),
            LGESBatteryChargeSensor(coordinator, station_id, device_info),
            LGESBatteryDischargeSensor(coordinator, station_id, device_info),
            LGESConsumptionSensor(coordinator, station_id, device_info),
            
            # Monthly energy stats from GetChartByPlant - Range=3
            LGESMonthlyGenerationSensor(coordinator, station_id, device_info),
            LGESMonthlyGridImportSensor(coordinator, station_id, device_info),
            LGESMonthlyGridExportSensor(coordinator, station_id, device_info),
            LGESMonthlySelfUseSensor(coordinator, station_id, device_info),
            LGESMonthlyBatteryChargeSensor(coordinator, station_id, device_info),
            LGESMonthlyBatteryDischargeSensor(coordinator, station_id, device_info),
            LGESMonthlyConsumptionSensor(coordinator, station_id, device_info),
            
            # Yearly energy stats from GetChartByPlant - Range=4
            LGESYearlyGenerationSensor(coordinator, station_id, device_info),
            LGESYearlyGridImportSensor(coordinator, station_id, device_info),
            LGESYearlyGridExportSensor(coordinator, station_id, device_info),
            LGESYearlySelfUseSensor(coordinator, station_id, device_info),
            LGESYearlyBatteryChargeSensor(coordinator, station_id, device_info),
            LGESYearlyBatteryDischargeSensor(coordinator, station_id, device_info),
            LGESYearlyConsumptionSensor(coordinator, station_id, device_info),
            
            # All-time energy stats from GetChartByPlant - Range=1
            LGESAllTimeGenerationSensor(coordinator, station_id, device_info),
            LGESAllTimeGridImportSensor(coordinator, station_id, device_info),
            LGESAllTimeGridExportSensor(coordinator, station_id, device_info),
            LGESAllTimeSelfUseSensor(coordinator, station_id, device_info),
            LGESAllTimeBatteryChargeSensor(coordinator, station_id, device_info),
            LGESAllTimeBatteryDischargeSensor(coordinator, station_id, device_info),
            LGESAllTimeConsumptionSensor(coordinator, station_id, device_info),
            
            # Income sensors
            LGESDailyIncomeSensor(coordinator, station_id, device_info),
            LGESTotalIncomeSensor(coordinator, station_id, device_info),
            
            # System info sensors
            LGESStatusSensor(coordinator, station_id, device_info),
            LGESSolarCapacitySensor(coordinator, station_id, device_info),
            LGESLastUpdateSensor(coordinator, station_id, device_info),
        ])
        
        # Add battery-specific sensors for each battery in soc array
        soc_list = details.get("soc", [])
        for idx, battery in enumerate(soc_list):
            battery_sn = battery.get("sn", f"Battery {idx + 1}")
            entities.append(
                LGESBatteryUnitSensor(coordinator, station_id, device_info, idx, battery_sn)
            )
    
    async_add_entities(entities)


class LGESSensor(CoordinatorEntity[LGESDataUpdateCoordinator], SensorEntity):
    """Base class for LG Energy Solutions sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LGESDataUpdateCoordinator,
        station_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_device_info = device_info

    @property
    def station_data(self) -> dict[str, Any]:
        """Get the current station data."""
        return self.coordinator.data.get(self._station_id, {})

    @property
    def details(self) -> dict[str, Any]:
        """Get the details data."""
        return self.station_data.get("details", {})

    @property
    def powerflow(self) -> dict[str, Any]:
        """Get the powerflow data."""
        return self.station_data.get("powerflow", {})

    @property
    def info(self) -> dict[str, Any]:
        """Get the info section from details."""
        return self.details.get("info", {})

    @property
    def kpi(self) -> dict[str, Any]:
        """Get the KPI section from details."""
        return self.details.get("kpi", {})

    @property
    def soc_list(self) -> list[dict[str, Any]]:
        """Get the SOC (battery) list from details."""
        return self.details.get("soc", [])

    @property
    def powerflow_data(self) -> dict[str, Any]:
        """Get the powerflow sub-object from powerflow or details."""
        # Try powerflow response first
        pf = self.powerflow.get("powerflow", {})
        if pf:
            return pf
        # Also check details response
        return self.details.get("powerflow", {})

    @property
    def energy_stats(self) -> dict[str, Any]:
        """Get the daily energy stats from GetChartByPlant with Range=2."""
        return self.station_data.get("energy_stats", {})

    @property
    def model_data(self) -> dict[str, Any]:
        """Get the modelData from daily energy stats (contains buy/sell/charge etc)."""
        return self.energy_stats.get("modelData", {})

    @property
    def monthly_energy_stats(self) -> dict[str, Any]:
        """Get the monthly energy stats from GetChartByPlant with Range=3."""
        return self.station_data.get("monthly_energy_stats", {})

    @property
    def monthly_model_data(self) -> dict[str, Any]:
        """Get the modelData from monthly energy stats (contains this month's buy/sell/charge etc)."""
        return self.monthly_energy_stats.get("modelData", {})

    @property
    def yearly_energy_stats(self) -> dict[str, Any]:
        """Get the yearly energy stats from GetChartByPlant with Range=4."""
        return self.station_data.get("yearly_energy_stats", {})

    @property
    def yearly_model_data(self) -> dict[str, Any]:
        """Get the modelData from yearly energy stats (contains this year's buy/sell/charge etc)."""
        return self.yearly_energy_stats.get("modelData", {})

    @property
    def all_time_energy_stats(self) -> dict[str, Any]:
        """Get the all-time energy stats from GetChartByPlant with Range=1."""
        return self.station_data.get("all_time_energy_stats", {})

    @property
    def all_time_model_data(self) -> dict[str, Any]:
        """Get the modelData from all-time energy stats (contains lifetime buy/sell/charge etc)."""
        return self.all_time_energy_stats.get("modelData", {})

    def parse_power_value(self, value: Any) -> float | None:
        """Parse power value from string like '582.0W' or '-1252.0W'."""
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            import re
            match = re.match(r'^(-?[\d.]+)\s*(kW|W)?$', value, re.IGNORECASE)
            if match:
                num = float(match.group(1))
                unit = match.group(2)
                if unit and unit.lower() == 'kw':
                    num *= 1000
                return num
        
        return None


class LGESSolarPowerSensor(LGESSensor):
    """Sensor for real-time solar PV power."""

    _attr_translation_key = "solar_power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:solar-power"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_solar_power"

    @property
    def native_value(self) -> float | None:
        """Return the solar PV power."""
        pv = self.powerflow_data.get("pv")
        return self.parse_power_value(pv)


class LGESBatteryPowerSensor(LGESSensor):
    """Sensor for real-time battery power (charging/discharging)."""

    _attr_translation_key = "battery_power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_power"

    @property
    def native_value(self) -> float | None:
        """Return the battery power (positive = discharging, negative = charging)."""
        # Note: API has a typo - field is "bettery" not "battery"
        battery = self.powerflow_data.get("bettery") or self.powerflow_data.get("battery")
        return self.parse_power_value(battery)

    @property
    def icon(self) -> str:
        """Return icon based on charging state."""
        value = self.native_value
        if value is None:
            return "mdi:battery-unknown"
        if value > 0:
            return "mdi:battery-arrow-down"  # Discharging
        if value < 0:
            return "mdi:battery-arrow-up"  # Charging
        return "mdi:battery"


class LGESLoadPowerSensor(LGESSensor):
    """Sensor for real-time home load power."""

    _attr_translation_key = "load_power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_load_power"

    @property
    def native_value(self) -> float | None:
        """Return the home load power."""
        load = self.powerflow_data.get("load")
        return self.parse_power_value(load)


class LGESGridPowerSensor(LGESSensor):
    """Sensor for real-time grid power (import/export)."""

    _attr_translation_key = "grid_power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_power"

    @property
    def native_value(self) -> float | None:
        """Return the grid power (positive = importing, negative = exporting)."""
        grid = self.powerflow_data.get("grid")
        return self.parse_power_value(grid)

    @property
    def icon(self) -> str:
        """Return icon based on grid flow direction."""
        value = self.native_value
        if value is None:
            return "mdi:transmission-tower"
        if value > 0:
            return "mdi:transmission-tower-import"  # Importing from grid
        if value < 0:
            return "mdi:transmission-tower-export"  # Exporting to grid
        return "mdi:transmission-tower"


class LGESDailyGenerationSensor(LGESSensor):
    """Sensor for today's solar generation (from modelData.sum in chart data)."""

    _attr_translation_key = "daily_generation"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:solar-power-variant"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_daily_generation"

    @property
    def native_value(self) -> float | None:
        """Return today's generation in kWh (from modelData.sum)."""
        generation = self.model_data.get("sum")
        if generation is not None:
            return float(generation)
        return None


class LGESGridImportSensor(LGESSensor):
    """Sensor for daily grid import (energy bought from grid)."""

    _attr_translation_key = "grid_import"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_import"

    @property
    def native_value(self) -> float | None:
        """Return today's grid import in kWh."""
        buy = self.model_data.get("buy")
        if buy is not None:
            return float(buy)
        return None


class LGESGridExportSensor(LGESSensor):
    """Sensor for daily grid export (energy sold to grid)."""

    _attr_translation_key = "grid_export"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-export"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_export"

    @property
    def native_value(self) -> float | None:
        """Return today's grid export in kWh."""
        sell = self.model_data.get("sell")
        if sell is not None:
            return float(sell)
        return None


class LGESSelfUseSensor(LGESSensor):
    """Sensor for daily self-consumed solar energy."""

    _attr_translation_key = "self_use"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_self_use"

    @property
    def native_value(self) -> float | None:
        """Return today's self-consumed solar in kWh."""
        self_use = self.model_data.get("selfUseOfPv")
        if self_use is not None:
            return float(self_use)
        return None


class LGESBatteryChargeSensor(LGESSensor):
    """Sensor for daily battery charge energy."""

    _attr_translation_key = "battery_charge"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-charging"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_charge"

    @property
    def native_value(self) -> float | None:
        """Return today's battery charge in kWh."""
        charge = self.model_data.get("charge")
        if charge is not None:
            return float(charge)
        return None


class LGESBatteryDischargeSensor(LGESSensor):
    """Sensor for daily battery discharge energy."""

    _attr_translation_key = "battery_discharge"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-arrow-down"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_discharge"

    @property
    def native_value(self) -> float | None:
        """Return today's battery discharge in kWh."""
        discharge = self.model_data.get("disCharge")
        if discharge is not None:
            return float(discharge)
        return None


class LGESConsumptionSensor(LGESSensor):
    """Sensor for daily home consumption."""

    _attr_translation_key = "consumption"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_consumption"

    @property
    def native_value(self) -> float | None:
        """Return today's home consumption in kWh."""
        consumption = self.model_data.get("consumptionOfLoad")
        if consumption is not None:
            return float(consumption)
        return None


class LGESBatterySOCSensor(LGESSensor):
    """Sensor for battery state of charge."""

    _attr_translation_key = "battery_soc"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_soc"

    @property
    def native_value(self) -> float | None:
        """Return the battery SOC."""
        soc_list = self.soc_list
        if soc_list:
            # Get the first battery's SOC (power field contains percentage)
            power = soc_list[0].get("power")
            if power is not None:
                return float(power)
        return None

    @property
    def icon(self) -> str:
        """Return dynamic battery icon based on level."""
        value = self.native_value
        if value is None:
            return "mdi:battery-unknown"
        if value >= 95:
            return "mdi:battery"
        if value >= 85:
            return "mdi:battery-90"
        if value >= 75:
            return "mdi:battery-80"
        if value >= 65:
            return "mdi:battery-70"
        if value >= 55:
            return "mdi:battery-60"
        if value >= 45:
            return "mdi:battery-50"
        if value >= 35:
            return "mdi:battery-40"
        if value >= 25:
            return "mdi:battery-30"
        if value >= 15:
            return "mdi:battery-20"
        if value >= 5:
            return "mdi:battery-10"
        return "mdi:battery-outline"


class LGESBatteryCapacitySensor(LGESSensor):
    """Sensor for battery capacity."""

    _attr_translation_key = "battery_capacity"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY_STORAGE
    _attr_icon = "mdi:battery-high"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_capacity"

    @property
    def native_value(self) -> float | None:
        """Return the battery capacity."""
        capacity = self.info.get("battery_capacity")
        if capacity is not None:
            return float(capacity)
        return None



class LGESDailyIncomeSensor(LGESSensor):
    """Sensor for daily income."""

    _attr_translation_key = "daily_income"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_daily_income"

    @property
    def native_value(self) -> float | None:
        """Return daily income."""
        value = self.kpi.get("day_income")
        if value is not None:
            return float(value)
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency unit."""
        return self.kpi.get("currency", "AUD")


class LGESTotalIncomeSensor(LGESSensor):
    """Sensor for total lifetime income."""

    _attr_translation_key = "total_income"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_total_income"

    @property
    def native_value(self) -> float | None:
        """Return total income."""
        value = self.kpi.get("total_income")
        if value is not None:
            return float(value)
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency unit."""
        return self.kpi.get("currency", "AUD")


class LGESStatusSensor(LGESSensor):
    """Sensor for system status."""

    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["online", "offline", "error", "waiting", "unknown"]

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_status"

    @property
    def native_value(self) -> str:
        """Return the status."""
        status = self.info.get("status")
        if status is None:
            return "unknown"
        
        status_map = {
            -1: "error",
            0: "offline",
            1: "online",
            2: "waiting",
        }
        return status_map.get(status, "unknown")

    @property
    def icon(self) -> str:
        """Return icon based on status."""
        status = self.info.get("status")
        if status == 1:
            return "mdi:check-circle"
        if status == 0:
            return "mdi:power-off"
        if status == -1:
            return "mdi:alert-circle"
        return "mdi:help-circle"


class LGESSolarCapacitySensor(LGESSensor):
    """Sensor for solar panel capacity."""

    _attr_translation_key = "solar_capacity"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_icon = "mdi:solar-panel-large"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_solar_capacity"

    @property
    def native_value(self) -> float | None:
        """Return solar capacity."""
        value = self.info.get("capacity")
        if value is not None:
            return float(value)
        return None


class LGESLastUpdateSensor(LGESSensor):
    """Sensor for last update time."""

    _attr_translation_key = "last_update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_last_update"

    @property
    def native_value(self) -> datetime | None:
        """Return the last update time."""
        from datetime import timezone, timedelta
        
        local_date = self.info.get("local_date")
        if local_date:
            try:
                # Parse format: "2025-12-09 17:46:59"
                dt = datetime.strptime(local_date, "%Y-%m-%d %H:%M:%S")
                
                # Get timezone offset from API (time_span is negative, e.g., -10 for GMT+10)
                time_span = self.info.get("time_span", 0)
                # Convert to positive offset (API returns -10 for UTC+10)
                offset_hours = -time_span if time_span else 0
                tz = timezone(timedelta(hours=offset_hours))
                
                return dt.replace(tzinfo=tz)
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Could not parse date '%s': %s", local_date, err)
        return None


class LGESBatteryUnitSensor(LGESSensor):
    """Sensor for individual battery unit."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, station_id, device_info, battery_index: int, battery_sn: str):
        super().__init__(coordinator, station_id, device_info)
        self._battery_index = battery_index
        self._battery_sn = battery_sn
        self._attr_unique_id = f"{station_id}_battery_{battery_index}"
        self._attr_name = f"Battery {battery_index + 1} ({battery_sn[-8:]})"

    @property
    def native_value(self) -> float | None:
        """Return the battery SOC."""
        soc_list = self.soc_list
        if len(soc_list) > self._battery_index:
            power = soc_list[self._battery_index].get("power")
            if power is not None:
                return float(power)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional battery attributes."""
        soc_list = self.soc_list
        if len(soc_list) > self._battery_index:
            battery = soc_list[self._battery_index]
            return {
                "serial_number": battery.get("sn"),
                "status": battery.get("status"),
                "local": battery.get("local"),
            }
        return {}


# All-Time Energy Sensors (from GetChartByPlant with Range=1)

class LGESAllTimeGenerationSensor(LGESSensor):
    """Sensor for all-time solar generation (from modelData.sum with Range=1)."""

    _attr_translation_key = "generation_all_time"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:solar-power-variant"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_generation_all_time"

    @property
    def native_value(self) -> float | None:
        """Return all-time generation in kWh (all-time + today for real-time accuracy)."""
        all_time = self.all_time_model_data.get("sum")
        today = self.model_data.get("sum")
        if all_time is not None:
            total = float(all_time)
            if today is not None:
                total += float(today)
            return total
        return None


class LGESAllTimeGridImportSensor(LGESSensor):
    """Sensor for all-time grid import (total energy bought from grid)."""

    _attr_translation_key = "grid_import_all_time"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_import_all_time"

    @property
    def native_value(self) -> float | None:
        """Return all-time grid import in kWh (all-time + today for real-time accuracy)."""
        all_time = self.all_time_model_data.get("buy")
        today = self.model_data.get("buy")
        if all_time is not None:
            total = float(all_time)
            if today is not None:
                total += float(today)
            return total
        return None


class LGESAllTimeGridExportSensor(LGESSensor):
    """Sensor for all-time grid export (total energy sold to grid)."""

    _attr_translation_key = "grid_export_all_time"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-export"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_export_all_time"

    @property
    def native_value(self) -> float | None:
        """Return all-time grid export in kWh (all-time + today for real-time accuracy)."""
        all_time = self.all_time_model_data.get("sell")
        today = self.model_data.get("sell")
        if all_time is not None:
            total = float(all_time)
            if today is not None:
                total += float(today)
            return total
        return None


class LGESAllTimeSelfUseSensor(LGESSensor):
    """Sensor for all-time self-consumed solar energy."""

    _attr_translation_key = "self_use_all_time"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_self_use_all_time"

    @property
    def native_value(self) -> float | None:
        """Return all-time self-consumed solar in kWh (all-time + today for real-time accuracy)."""
        all_time = self.all_time_model_data.get("selfUseOfPv")
        today = self.model_data.get("selfUseOfPv")
        if all_time is not None:
            total = float(all_time)
            if today is not None:
                total += float(today)
            return total
        return None


class LGESAllTimeBatteryChargeSensor(LGESSensor):
    """Sensor for all-time battery charge energy."""

    _attr_translation_key = "battery_charge_all_time"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-charging"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_charge_all_time"

    @property
    def native_value(self) -> float | None:
        """Return all-time battery charge in kWh (all-time + today for real-time accuracy)."""
        all_time = self.all_time_model_data.get("charge")
        today = self.model_data.get("charge")
        if all_time is not None:
            total = float(all_time)
            if today is not None:
                total += float(today)
            return total
        return None


class LGESAllTimeBatteryDischargeSensor(LGESSensor):
    """Sensor for all-time battery discharge energy."""

    _attr_translation_key = "battery_discharge_all_time"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-arrow-down"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_discharge_all_time"

    @property
    def native_value(self) -> float | None:
        """Return all-time battery discharge in kWh (all-time + today for real-time accuracy)."""
        all_time = self.all_time_model_data.get("disCharge")
        today = self.model_data.get("disCharge")
        if all_time is not None:
            total = float(all_time)
            if today is not None:
                total += float(today)
            return total
        return None


class LGESAllTimeConsumptionSensor(LGESSensor):
    """Sensor for all-time home consumption."""

    _attr_translation_key = "consumption_all_time"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_consumption_all_time"

    @property
    def native_value(self) -> float | None:
        """Return all-time home consumption in kWh (all-time + today for real-time accuracy)."""
        all_time = self.all_time_model_data.get("consumptionOfLoad")
        today = self.model_data.get("consumptionOfLoad")
        if all_time is not None:
            total = float(all_time)
            if today is not None:
                total += float(today)
            return total
        return None


# Monthly Energy Sensors (from GetChartByPlant with Range=3)

class LGESMonthlyGenerationSensor(LGESSensor):
    """Sensor for this month's solar generation."""

    _attr_translation_key = "generation_this_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:solar-power-variant"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_generation_this_month"

    @property
    def native_value(self) -> float | None:
        """Return this month's generation in kWh."""
        generation = self.monthly_model_data.get("sum")
        if generation is not None:
            return float(generation)
        return None


class LGESMonthlyGridImportSensor(LGESSensor):
    """Sensor for this month's grid import."""

    _attr_translation_key = "grid_import_this_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_import_this_month"

    @property
    def native_value(self) -> float | None:
        """Return this month's grid import in kWh."""
        buy = self.monthly_model_data.get("buy")
        if buy is not None:
            return float(buy)
        return None


class LGESMonthlyGridExportSensor(LGESSensor):
    """Sensor for this month's grid export."""

    _attr_translation_key = "grid_export_this_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-export"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_export_this_month"

    @property
    def native_value(self) -> float | None:
        """Return this month's grid export in kWh."""
        sell = self.monthly_model_data.get("sell")
        if sell is not None:
            return float(sell)
        return None


class LGESMonthlySelfUseSensor(LGESSensor):
    """Sensor for this month's self-consumed solar energy."""

    _attr_translation_key = "self_use_this_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_self_use_this_month"

    @property
    def native_value(self) -> float | None:
        """Return this month's self-consumed solar in kWh."""
        self_use = self.monthly_model_data.get("selfUseOfPv")
        if self_use is not None:
            return float(self_use)
        return None


class LGESMonthlyBatteryChargeSensor(LGESSensor):
    """Sensor for this month's battery charge energy."""

    _attr_translation_key = "battery_charge_this_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-charging"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_charge_this_month"

    @property
    def native_value(self) -> float | None:
        """Return this month's battery charge in kWh."""
        charge = self.monthly_model_data.get("charge")
        if charge is not None:
            return float(charge)
        return None


class LGESMonthlyBatteryDischargeSensor(LGESSensor):
    """Sensor for this month's battery discharge energy."""

    _attr_translation_key = "battery_discharge_this_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-arrow-down"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_discharge_this_month"

    @property
    def native_value(self) -> float | None:
        """Return this month's battery discharge in kWh."""
        discharge = self.monthly_model_data.get("disCharge")
        if discharge is not None:
            return float(discharge)
        return None


class LGESMonthlyConsumptionSensor(LGESSensor):
    """Sensor for this month's home consumption."""

    _attr_translation_key = "consumption_this_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_consumption_this_month"

    @property
    def native_value(self) -> float | None:
        """Return this month's home consumption in kWh."""
        consumption = self.monthly_model_data.get("consumptionOfLoad")
        if consumption is not None:
            return float(consumption)
        return None


# Yearly Energy Sensors (from GetChartByPlant with Range=4)

class LGESYearlyGenerationSensor(LGESSensor):
    """Sensor for this year's solar generation."""

    _attr_translation_key = "generation_this_year"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:solar-power-variant"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_generation_this_year"

    @property
    def native_value(self) -> float | None:
        """Return this year's generation in kWh."""
        generation = self.yearly_model_data.get("sum")
        if generation is not None:
            return float(generation)
        return None


class LGESYearlyGridImportSensor(LGESSensor):
    """Sensor for this year's grid import."""

    _attr_translation_key = "grid_import_this_year"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_import_this_year"

    @property
    def native_value(self) -> float | None:
        """Return this year's grid import in kWh."""
        buy = self.yearly_model_data.get("buy")
        if buy is not None:
            return float(buy)
        return None


class LGESYearlyGridExportSensor(LGESSensor):
    """Sensor for this year's grid export."""

    _attr_translation_key = "grid_export_this_year"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:transmission-tower-export"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_grid_export_this_year"

    @property
    def native_value(self) -> float | None:
        """Return this year's grid export in kWh."""
        sell = self.yearly_model_data.get("sell")
        if sell is not None:
            return float(sell)
        return None


class LGESYearlySelfUseSensor(LGESSensor):
    """Sensor for this year's self-consumed solar energy."""

    _attr_translation_key = "self_use_this_year"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_self_use_this_year"

    @property
    def native_value(self) -> float | None:
        """Return this year's self-consumed solar in kWh."""
        self_use = self.yearly_model_data.get("selfUseOfPv")
        if self_use is not None:
            return float(self_use)
        return None


class LGESYearlyBatteryChargeSensor(LGESSensor):
    """Sensor for this year's battery charge energy."""

    _attr_translation_key = "battery_charge_this_year"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-charging"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_charge_this_year"

    @property
    def native_value(self) -> float | None:
        """Return this year's battery charge in kWh."""
        charge = self.yearly_model_data.get("charge")
        if charge is not None:
            return float(charge)
        return None


class LGESYearlyBatteryDischargeSensor(LGESSensor):
    """Sensor for this year's battery discharge energy."""

    _attr_translation_key = "battery_discharge_this_year"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-arrow-down"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_battery_discharge_this_year"

    @property
    def native_value(self) -> float | None:
        """Return this year's battery discharge in kWh."""
        discharge = self.yearly_model_data.get("disCharge")
        if discharge is not None:
            return float(discharge)
        return None


class LGESYearlyConsumptionSensor(LGESSensor):
    """Sensor for this year's home consumption."""

    _attr_translation_key = "consumption_this_year"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, station_id, device_info):
        super().__init__(coordinator, station_id, device_info)
        self._attr_unique_id = f"{station_id}_consumption_this_year"

    @property
    def native_value(self) -> float | None:
        """Return this year's home consumption in kWh."""
        consumption = self.yearly_model_data.get("consumptionOfLoad")
        if consumption is not None:
            return float(consumption)
        return None
