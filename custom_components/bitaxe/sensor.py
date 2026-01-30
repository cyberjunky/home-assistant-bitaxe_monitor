"""Sensor platform for Bitaxe integration."""
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
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BitaxeDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class BitaxeSensorEntityDescription(SensorEntityDescription):
    """Describes Bitaxe sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda _: None
    # If True, sensor is always created (for computed values)
    always_create: bool = False


# All possible sensor descriptions - only created if the key exists in API data
SENSOR_DESCRIPTIONS: tuple[BitaxeSensorEntityDescription, ...] = (
    # ==========================================================================
    # Power & Electrical
    # ==========================================================================
    BitaxeSensorEntityDescription(
        key="power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("power"),
        icon="mdi:flash",
    ),
    BitaxeSensorEntityDescription(
        key="maxPower",
        name="Max Power Limit",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("maxPower"),
        icon="mdi:flash-alert",
    ),
    BitaxeSensorEntityDescription(
        key="voltage",
        name="Input Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("voltage"),
        icon="mdi:sine-wave",
    ),
    BitaxeSensorEntityDescription(
        key="nominalVoltage",
        name="Nominal Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("nominalVoltage"),
        icon="mdi:sine-wave",
    ),
    BitaxeSensorEntityDescription(
        key="current",
        name="Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            round(data.get("current", 0) / 1000, 2) if data.get("current") else None
        ),
        icon="mdi:current-ac",
    ),
    BitaxeSensorEntityDescription(
        key="coreVoltage",
        name="Core Voltage Target",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("coreVoltage"),
        icon="mdi:chip",
    ),
    BitaxeSensorEntityDescription(
        key="coreVoltageActual",
        name="Core Voltage Actual",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("coreVoltageActual"),
        icon="mdi:chip",
    ),
    # ==========================================================================
    # Temperature
    # ==========================================================================
    BitaxeSensorEntityDescription(
        key="temp",
        name="ASIC Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("temp"),
        icon="mdi:thermometer",
    ),
    BitaxeSensorEntityDescription(
        key="temp2",
        name="ASIC Temperature 2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("temp2"),
        icon="mdi:thermometer",
    ),
    BitaxeSensorEntityDescription(
        key="vrTemp",
        name="VR Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("vrTemp"),
        icon="mdi:thermometer-alert",
    ),
    BitaxeSensorEntityDescription(
        key="temptarget",
        name="Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("temptarget"),
        icon="mdi:thermometer-check",
    ),
    # ==========================================================================
    # Performance / Hash Rate
    # ==========================================================================
    BitaxeSensorEntityDescription(
        key="hashRate",
        name="Hash Rate",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("hashRate"),
        icon="mdi:speedometer",
    ),
    BitaxeSensorEntityDescription(
        key="hashRate_1m",
        name="Hash Rate (1m avg)",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("hashRate_1m"),
        icon="mdi:speedometer",
    ),
    BitaxeSensorEntityDescription(
        key="hashRate_10m",
        name="Hash Rate (10m avg)",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("hashRate_10m"),
        icon="mdi:speedometer",
    ),
    BitaxeSensorEntityDescription(
        key="hashRate_1h",
        name="Hash Rate (1h avg)",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("hashRate_1h"),
        icon="mdi:speedometer",
    ),
    BitaxeSensorEntityDescription(
        key="hashRate_1d",
        name="Hash Rate (1d avg)",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("hashRate_1d"),
        icon="mdi:speedometer",
    ),
    BitaxeSensorEntityDescription(
        key="expectedHashrate",
        name="Expected Hash Rate",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("expectedHashrate"),
        icon="mdi:speedometer-medium",
    ),
    BitaxeSensorEntityDescription(
        key="frequency",
        name="ASIC Frequency",
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("frequency"),
        icon="mdi:sine-wave",
    ),
    BitaxeSensorEntityDescription(
        key="smallCoreCount",
        name="ASIC Core Count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("smallCoreCount"),
        icon="mdi:cpu-64-bit",
    ),
    BitaxeSensorEntityDescription(
        key="errorPercentage",
        name="Error Rate",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("errorPercentage"),
        icon="mdi:alert-circle-outline",
    ),
    # Computed efficiency - always create if we have power and hashRate
    BitaxeSensorEntityDescription(
        key="efficiency",
        name="Efficiency",
        native_unit_of_measurement="J/TH",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            round(data.get("power", 0) / (data.get("hashRate", 1) / 1000), 2)
            if data.get("hashRate", 0) > 0
            else None
        ),
        icon="mdi:leaf",
        always_create=True,
    ),
    # ==========================================================================
    # Difficulty & Mining Stats
    # ==========================================================================
    BitaxeSensorEntityDescription(
        key="bestDiff",
        name="Best Difficulty (All Time)",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("bestDiff"),
        icon="mdi:trophy",
    ),
    BitaxeSensorEntityDescription(
        key="bestSessionDiff",
        name="Best Difficulty (Session)",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("bestSessionDiff"),
        icon="mdi:trophy-outline",
    ),
    BitaxeSensorEntityDescription(
        key="poolDifficulty",
        name="Pool Difficulty",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("poolDifficulty"),
        icon="mdi:target",
    ),
    BitaxeSensorEntityDescription(
        key="networkDifficulty",
        name="Network Difficulty",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("networkDifficulty"),
        icon="mdi:earth",
    ),
    BitaxeSensorEntityDescription(
        key="blockHeight",
        name="Block Height",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("blockHeight"),
        icon="mdi:cube-outline",
    ),
    # ==========================================================================
    # Share Counters
    # ==========================================================================
    BitaxeSensorEntityDescription(
        key="sharesAccepted",
        name="Shares Accepted",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("sharesAccepted"),
        icon="mdi:check-circle",
    ),
    BitaxeSensorEntityDescription(
        key="sharesRejected",
        name="Shares Rejected",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("sharesRejected"),
        icon="mdi:close-circle",
    ),
    BitaxeSensorEntityDescription(
        key="blockFound",
        name="Blocks Found",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("blockFound"),
        icon="mdi:cube",
    ),
    # Legacy key for blocks found
    BitaxeSensorEntityDescription(
        key="foundBlocks",
        name="Blocks Found",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("foundBlocks"),
        icon="mdi:cube",
    ),
    # ==========================================================================
    # Fan & Cooling
    # ==========================================================================
    BitaxeSensorEntityDescription(
        key="fanspeed",
        name="Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("fanspeed"),
        icon="mdi:fan",
    ),
    BitaxeSensorEntityDescription(
        key="fanrpm",
        name="Fan RPM",
        native_unit_of_measurement="RPM",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("fanrpm"),
        icon="mdi:fan",
    ),
    BitaxeSensorEntityDescription(
        key="fan2rpm",
        name="Fan 2 RPM",
        native_unit_of_measurement="RPM",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("fan2rpm"),
        icon="mdi:fan",
    ),
    BitaxeSensorEntityDescription(
        key="autofanspeed",
        name="Auto Fan Speed",
        value_fn=lambda data: "On" if data.get("autofanspeed") else "Off",
        icon="mdi:fan-auto",
    ),
    BitaxeSensorEntityDescription(
        key="manualFanSpeed",
        name="Manual Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("manualFanSpeed"),
        icon="mdi:fan-speed-1",
    ),
    BitaxeSensorEntityDescription(
        key="minFanSpeed",
        name="Minimum Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("minFanSpeed"),
        icon="mdi:fan-speed-1",
    ),
    # ==========================================================================
    # Network & Connectivity
    # ==========================================================================
    BitaxeSensorEntityDescription(
        key="wifiRSSI",
        name="WiFi Signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("wifiRSSI"),
        icon="mdi:wifi",
    ),
    BitaxeSensorEntityDescription(
        key="responseTime",
        name="Pool Response Time",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("responseTime"),
        icon="mdi:timer-outline",
    ),
    # ==========================================================================
    # System Status
    # ==========================================================================
    BitaxeSensorEntityDescription(
        key="uptimeSeconds",
        name="Uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("uptimeSeconds"),
        icon="mdi:clock-outline",
    ),
    BitaxeSensorEntityDescription(
        key="freeHeap",
        name="Free Memory",
        native_unit_of_measurement="B",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("freeHeap"),
        icon="mdi:memory",
        entity_registry_enabled_default=False,
    ),
    BitaxeSensorEntityDescription(
        key="overheat_mode",
        name="Overheat Mode",
        value_fn=lambda data: "Active" if data.get("overheat_mode") else "Normal",
        icon="mdi:thermometer-alert",
    ),
    BitaxeSensorEntityDescription(
        key="overclockEnabled",
        name="Overclock",
        value_fn=lambda data: "Enabled" if data.get("overclockEnabled") else "Disabled",
        icon="mdi:speedometer",
    ),
)


def _should_create_sensor(
    description: BitaxeSensorEntityDescription, data: dict[str, Any]
) -> bool:
    """Determine if a sensor should be created based on available data."""
    if description.always_create:
        return True
    return description.key in data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bitaxe sensor based on a config entry."""
    coordinator: BitaxeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}

    entities: list[BitaxeSensor] = []

    # Add sensors only if their key exists in the data (auto-detection)
    for description in SENSOR_DESCRIPTIONS:
        if _should_create_sensor(description, data):
            entities.append(BitaxeSensor(coordinator, description, entry))

    # Dynamically create ASIC temp sensors based on actual data (asicTemps array)
    asic_temps = data.get("asicTemps", [])
    for i in range(len(asic_temps)):
        entities.append(
            BitaxeSensor(
                coordinator,
                BitaxeSensorEntityDescription(
                    key=f"asicTemp{i + 1}",
                    name=f"ASIC {i + 1} Temperature",
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    value_fn=lambda d, idx=i: (
                        d.get("asicTemps", [])[idx]
                        if len(d.get("asicTemps", [])) > idx
                        else None
                    ),
                    icon="mdi:thermometer",
                ),
                entry,
            )
        )

    # Dynamically create per-ASIC hash rate sensors from hashrateMonitor
    hashrate_monitor = data.get("hashrateMonitor", {})
    asics = hashrate_monitor.get("asics", [])
    for i, asic_data in enumerate(asics):
        # Total hash rate for this ASIC
        entities.append(
            BitaxeSensor(
                coordinator,
                BitaxeSensorEntityDescription(
                    key=f"asic{i + 1}_hashrate",
                    name=f"ASIC {i + 1} Hash Rate",
                    native_unit_of_measurement="GH/s",
                    state_class=SensorStateClass.MEASUREMENT,
                    value_fn=lambda d, idx=i: (
                        d.get("hashrateMonitor", {}).get("asics", [])[idx].get("total")
                        if len(d.get("hashrateMonitor", {}).get("asics", [])) > idx
                        else None
                    ),
                    icon="mdi:speedometer",
                ),
                entry,
            )
        )
        # Error count for this ASIC
        entities.append(
            BitaxeSensor(
                coordinator,
                BitaxeSensorEntityDescription(
                    key=f"asic{i + 1}_errors",
                    name=f"ASIC {i + 1} Errors",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    value_fn=lambda d, idx=i: (
                        d.get("hashrateMonitor", {})
                        .get("asics", [])[idx]
                        .get("errorCount")
                        if len(d.get("hashrateMonitor", {}).get("asics", [])) > idx
                        else None
                    ),
                    icon="mdi:alert-circle",
                ),
                entry,
            )
        )

    async_add_entities(entities)


class BitaxeSensor(CoordinatorEntity[BitaxeDataUpdateCoordinator], SensorEntity):
    """Representation of a Bitaxe sensor."""

    entity_description: BitaxeSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BitaxeDataUpdateCoordinator,
        description: BitaxeSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Bitaxe",
            "model": coordinator.data.get("ASICModel", "Unknown"),
            "sw_version": coordinator.data.get("version", "Unknown"),
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
