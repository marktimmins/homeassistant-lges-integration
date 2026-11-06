"""Sensor platform for LG Energy Solutions."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LGESDataUpdateCoordinator

# SEMS+ status codes (as used by the Solarportal+ web portal).
STATUS_MAP = {
    -1: "error",
    0: "offline",
    1: "online",
    2: "error",  # fault
    3: "waiting",  # standby, e.g. no sun at night
    4: "offline",  # shut down
    5: "online",  # running
}
STATUS_ICONS = {
    "online": "mdi:check-circle",
    "waiting": "mdi:sleep",
    "offline": "mdi:power-off",
    "error": "mdi:alert-circle",
}


@dataclass(frozen=True, kw_only=True)
class LGESSensorEntityDescription(SensorEntityDescription):
    """Describes an LG Energy Solutions sensor.

    The key is also the translation key and the unique ID suffix, so it must
    never change for an existing sensor.
    """

    value_fn: Callable[[dict[str, Any]], Any]
    icon_fn: Callable[[Any], str] | None = None
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    # For sensors whose unit comes from the data (currency).
    unit_fn: Callable[[dict[str, Any]], str | None] | None = None


def _get(*path: str) -> Callable[[dict[str, Any]], Any]:
    """Return a function that reads a nested value from station data."""

    def read(data: Any) -> Any:
        for key in path:
            if not isinstance(data, dict):
                return None
            data = data.get(key)
        return data

    return read


def _signed_icon(positive: str, negative: str, zero: str) -> Callable[[Any], str]:
    """Icon that follows the sign of the value."""

    def icon(value: Any) -> str:
        if value is None:
            return zero
        return positive if value > 0 else negative if value < 0 else zero

    return icon


def _battery_level_icon(value: Any) -> str:
    """Battery icon in 10% steps."""
    if value is None:
        return "mdi:battery-unknown"
    if value >= 95:
        return "mdi:battery"
    if value < 5:
        return "mdi:battery-outline"
    return f"mdi:battery-{int((value + 5) // 10) * 10}"


def _status(data: dict[str, Any]) -> str:
    return STATUS_MAP.get(_get("info", "status")(data), "unknown")


def _active_alarms(data: dict[str, Any]) -> int | None:
    alarms = data.get("alarms")
    if alarms is None:
        return None
    return sum(1 for alarm in alarms if alarm.get("active"))


def _alarm_attributes(data: dict[str, Any]) -> dict[str, Any]:
    alarms = data.get("alarms") or []
    attributes: dict[str, Any] = {
        "active_alarms": [
            {key: alarm.get(key) for key in ("name", "device", "level", "started")}
            for alarm in alarms
            if alarm.get("active")
        ]
    }
    if alarms:
        latest = alarms[0]
        attributes["last_alarm"] = latest.get("name")
        attributes["last_alarm_started"] = latest.get("started")
        attributes["last_alarm_cleared"] = latest.get("cleared")
    return attributes


def _currency(data: dict[str, Any]) -> str:
    return _get("income", "currency")(data) or "AUD"


# Energy sensors: field in data["energy"][period] -> (today's key, icon).
# Other periods use f"{field}_{suffix}", e.g. "grid_import_this_month".
ENERGY_FIELDS = {
    "generation": ("daily_generation", "mdi:solar-power-variant"),
    "grid_import": ("grid_import", "mdi:transmission-tower-import"),
    "grid_export": ("grid_export", "mdi:transmission-tower-export"),
    "self_use": ("self_use", "mdi:home-lightning-bolt"),
    "battery_charge": ("battery_charge", "mdi:battery-charging"),
    "battery_discharge": ("battery_discharge", "mdi:battery-arrow-down"),
    "consumption": ("consumption", "mdi:home-lightning-bolt"),
}
ENERGY_PERIODS = {"month": "this_month", "year": "this_year", "all_time": "all_time"}


def _energy(key: str, period: str, field: str, icon: str) -> LGESSensorEntityDescription:
    return LGESSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon=icon,
        value_fn=_get("energy", period, field),
    )


def _percent(key: str, icon: str) -> LGESSensorEntityDescription:
    return LGESSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon=icon,
        value_fn=_get("rates", key),
    )


def _power(key: str, field: str, **kwargs: Any) -> LGESSensorEntityDescription:
    return LGESSensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get("power", field),
        **kwargs,
    )


SENSORS: tuple[LGESSensorEntityDescription, ...] = (
    # Live power
    _power("solar_power", "solar", icon="mdi:solar-power"),
    _power(
        "battery_power",
        "battery",
        # + discharging, - charging
        icon_fn=_signed_icon(
            "mdi:battery-arrow-down", "mdi:battery-arrow-up", "mdi:battery"
        ),
    ),
    _power("load_power", "load", icon="mdi:home-lightning-bolt"),
    _power(
        "grid_power",
        "grid",
        # + importing, - exporting
        icon_fn=_signed_icon(
            "mdi:transmission-tower-import",
            "mdi:transmission-tower-export",
            "mdi:transmission-tower",
        ),
    ),
    LGESSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        icon_fn=_battery_level_icon,
        value_fn=_get("power", "battery_soc"),
    ),
    # Energy today, this month, this year and all time
    *(
        _energy(today_key, "today", field, icon)
        for field, (today_key, icon) in ENERGY_FIELDS.items()
    ),
    *(
        _energy(f"{field}_{suffix}", period, field, icon)
        for period, suffix in ENERGY_PERIODS.items()
        for field, (_, icon) in ENERGY_FIELDS.items()
    ),
    _percent("self_consumption_rate", "mdi:home-percent"),
    _percent("self_sufficiency", "mdi:leaf"),
    # Income
    LGESSensorEntityDescription(
        key="daily_income",
        translation_key="daily_income",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:cash",
        value_fn=_get("income", "today"),
        unit_fn=_currency,
    ),
    LGESSensorEntityDescription(
        key="export_income_today",
        translation_key="export_income_today",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:cash-plus",
        value_fn=_get("income", "export_today"),
        unit_fn=_currency,
    ),
    LGESSensorEntityDescription(
        key="total_income",
        translation_key="total_income",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:cash-multiple",
        value_fn=_get("income", "total"),
        unit_fn=_currency,
    ),
    # System
    LGESSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["online", "offline", "error", "waiting", "unknown"],
        icon_fn=lambda value: STATUS_ICONS.get(value, "mdi:help-circle"),
        value_fn=_status,
    ),
    LGESSensorEntityDescription(
        key="active_alarms",
        translation_key="active_alarms",
        state_class=SensorStateClass.MEASUREMENT,
        icon_fn=lambda value: "mdi:alert" if value else "mdi:check-circle-outline",
        value_fn=_active_alarms,
        attributes_fn=_alarm_attributes,
    ),
    LGESSensorEntityDescription(
        key="solar_capacity",
        translation_key="solar_capacity",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:solar-panel-large",
        value_fn=_get("info", "capacity"),
    ),
    LGESSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        icon="mdi:battery-high",
        value_fn=_get("info", "battery_capacity"),
    ),
    LGESSensorEntityDescription(
        key="rated_power",
        translation_key="rated_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:flash",
        value_fn=_get("info", "rated_power"),
    ),
    # Inverter readings
    LGESSensorEntityDescription(
        key="inverter_temperature",
        translation_key="inverter_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get("inverter", "temperature"),
    ),
    LGESSensorEntityDescription(
        key="grid_voltage",
        translation_key="grid_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get("inverter", "grid_voltage"),
    ),
    LGESSensorEntityDescription(
        key="backup_power",
        translation_key="backup_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:power-plug-battery",
        value_fn=_get("inverter", "backup_power"),
    ),
    LGESSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value_fn=_get("info", "last_update"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LG Energy Solutions sensors based on a config entry."""
    coordinator: LGESDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for station_id, station in coordinator.data.items():
        info = station.get("info", {})
        device_info = DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            # The address is the most recognisable name for a home system.
            name=info.get("address") or info.get("name") or f"LGES Station {station_id[:8]}",
            manufacturer="LG Energy Solutions",
            model=info.get("model") or "Solar Inverter System",
            entry_type=DeviceEntryType.SERVICE,
        )
        entities.extend(
            LGESSensor(coordinator, station_id, device_info, description)
            for description in SENSORS
        )
        entities.extend(
            LGESBatteryUnitSensor(coordinator, station_id, device_info, index, battery)
            for index, battery in enumerate(station.get("batteries", []))
        )
        # One power and one voltage sensor per solar string the inverter reports.
        entities.extend(
            LGESSolarStringSensor(coordinator, station_id, device_info, number, measure)
            for number in station.get("inverter", {}).get("strings", {})
            for measure in ("power", "voltage")
        )

    async_add_entities(entities)


class LGESEntity(CoordinatorEntity[LGESDataUpdateCoordinator], SensorEntity):
    """Base class for a sensor that belongs to one station."""

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
    def station(self) -> dict[str, Any]:
        """Return this station's latest data."""
        return (self.coordinator.data or {}).get(self._station_id, {})

    @property
    def available(self) -> bool:
        """Return False if the last update had no data for this station."""
        return super().available and self._station_id in (self.coordinator.data or {})


class LGESSensor(LGESEntity):
    """A station sensor defined by an LGESSensorEntityDescription."""

    entity_description: LGESSensorEntityDescription

    def __init__(
        self,
        coordinator: LGESDataUpdateCoordinator,
        station_id: str,
        device_info: DeviceInfo,
        description: LGESSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station_id, device_info)
        self.entity_description = description
        self._attr_unique_id = f"{station_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.station)

    @property
    def icon(self) -> str | None:
        """Return the icon, which may depend on the value."""
        if self.entity_description.icon_fn:
            return self.entity_description.icon_fn(self.native_value)
        return super().icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit, which may come from the data."""
        if self.entity_description.unit_fn:
            return self.entity_description.unit_fn(self.station)
        return super().native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes, if the sensor has any."""
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.station)
        return None


class LGESSolarStringSensor(LGESEntity):
    """Power or voltage of one solar panel string (an MPPT input on the inverter)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: LGESDataUpdateCoordinator,
        station_id: str,
        device_info: DeviceInfo,
        number: int,
        measure: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station_id, device_info)
        self._number = number
        self._measure = measure
        self._attr_unique_id = f"{station_id}_pv{number}_{measure}"
        self._attr_name = f"Solar String {number} {measure.capitalize()}"
        if measure == "power":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_icon = "mdi:solar-panel"
        else:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    @property
    def native_value(self) -> float | None:
        """Return this string's latest reading."""
        strings = self.station.get("inverter", {}).get("strings", {})
        return strings.get(self._number, {}).get(self._measure)


class LGESBatteryUnitSensor(LGESEntity):
    """Charge level of one battery unit reported by a storage inverter."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: LGESDataUpdateCoordinator,
        station_id: str,
        device_info: DeviceInfo,
        index: int,
        battery: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station_id, device_info)
        self._index = index
        self._attr_unique_id = f"{station_id}_battery_{index}"
        self._attr_name = f"Battery {index + 1} ({str(battery.get('name', ''))[-8:]})"

    @property
    def battery(self) -> dict[str, Any]:
        """Return this battery's latest data."""
        batteries = self.station.get("batteries", [])
        return batteries[self._index] if self._index < len(batteries) else {}

    @property
    def native_value(self) -> float | None:
        """Return the battery's charge level."""
        return self.battery.get("soc")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the battery's identity and connection state."""
        battery = self.battery
        return {
            "serial_number": battery.get("name"),
            "status": battery.get("status"),
            "connected": battery.get("connected"),
        }
