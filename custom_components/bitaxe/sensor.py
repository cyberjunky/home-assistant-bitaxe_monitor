"""Sensor platform for Bitaxe integration."""


from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import BitaxeConfigEntry, BitaxeDataUpdateCoordinator
from .entity import BitaxeEntity

HASH_RATE_UNIT = "GH/s"

# SI suffixes used by AxeOS to abbreviate difficulty values
DIFFICULTY_SUFFIXES = ("", "k", "M", "G", "T", "P", "E")


def _parse_difficulty(value: object) -> float | None:
    """Return a difficulty as a number.

    Older firmware reports difficulties as abbreviated strings like "4.29G".
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str) or not (text := value.strip()):
        return None
    exponent = 0
    if text[-1] in DIFFICULTY_SUFFIXES[1:] or text[-1] == "K":
        exponent = "KMGTPE".index(text[-1].upper()) + 1
        text = text[:-1]
    try:
        return float(text) * 1000.0**exponent
    except ValueError:
        return None


def _format_difficulty(value: object) -> str | None:
    """Return a difficulty abbreviated like AxeOS does, e.g. 4.29G."""
    if (number := _parse_difficulty(value)) is None:
        return None
    exponent = 0
    while abs(number) >= 1000 and exponent < len(DIFFICULTY_SUFFIXES) - 1:
        number /= 1000
        exponent += 1
    return f"{number:.2f}".rstrip("0").rstrip(".") + DIFFICULTY_SUFFIXES[exponent]


def _scaled(key: str, factor: float, digits: int) -> Callable[[dict[str, Any]], Any]:
    """Return a value function that scales a numeric value."""

    def value_fn(data: dict[str, Any]) -> float | None:
        value = data.get(key)
        return round(value * factor, digits) if value is not None else None

    return value_fn


@dataclass(frozen=True, kw_only=True)
class BitaxeSensorEntityDescription(SensorEntityDescription):
    """Describes Bitaxe sensor entity."""

    # Defaults to the value of the API key equal to the entity key
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    # Whether the sensor is created, defaults to the entity key being in the data
    exists_fn: Callable[[dict[str, Any]], bool] | None = None


def _measurement(key: str, translation_key: str, **kwargs: Any) -> BitaxeSensorEntityDescription:
    """Return a description of a measurement sensor."""
    return BitaxeSensorEntityDescription(
        key=key,
        translation_key=translation_key,
        state_class=SensorStateClass.MEASUREMENT,
        **kwargs,
    )


def _temperature(key: str, translation_key: str, **kwargs: Any) -> BitaxeSensorEntityDescription:
    """Return a description of a temperature sensor."""
    return _measurement(
        key,
        translation_key,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        **kwargs,
    )


def _hash_rate(key: str, translation_key: str) -> BitaxeSensorEntityDescription:
    """Return a description of a hash rate sensor."""
    return _measurement(key, translation_key, native_unit_of_measurement=HASH_RATE_UNIT)


# Sensors are only created if their value is in the API data
SENSOR_DESCRIPTIONS: tuple[BitaxeSensorEntityDescription, ...] = (
    # Power & electrical
    _measurement(
        "power",
        "power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    _measurement(
        "maxPower",
        "max_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _measurement(
        "voltage",
        "input_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    _measurement(
        "nominalVoltage",
        "nominal_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _measurement(
        "current",
        "current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        # Reported in mA
        value_fn=_scaled("current", 0.001, 2),
    ),
    _measurement(
        "coreVoltage",
        "core_voltage_target",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    _measurement(
        "coreVoltageActual",
        "core_voltage_actual",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # Temperature
    _temperature("temp", "asic_temperature"),
    _temperature("temp2", "asic_temperature_2"),
    _temperature("vrTemp", "vr_temperature"),
    _temperature("vrTempInt", "vr_internal_temperature"),
    _temperature("temptarget", "target_temperature", entity_category=EntityCategory.DIAGNOSTIC),
    # Performance / hash rate
    _hash_rate("hashRate", "hash_rate"),
    _hash_rate("hashRate_1m", "hash_rate_1m"),
    _hash_rate("hashRate_10m", "hash_rate_10m"),
    _hash_rate("hashRate_1h", "hash_rate_1h"),
    _hash_rate("hashRate_1d", "hash_rate_1d"),
    _hash_rate("expectedHashrate", "expected_hash_rate"),
    _measurement(
        "frequency",
        "asic_frequency",
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    _measurement("smallCoreCount", "asic_core_count", entity_category=EntityCategory.DIAGNOSTIC),
    _measurement("errorPercentage", "error_rate", native_unit_of_measurement=PERCENTAGE),
    _measurement(
        "efficiency",
        "efficiency",
        native_unit_of_measurement="J/TH",
        value_fn=lambda data: (
            round(data["power"] / (data["hashRate"] / 1000), 2)
            if data.get("power") is not None and (data.get("hashRate") or 0) > 0
            else None
        ),
        exists_fn=lambda data: "power" in data and "hashRate" in data,
    ),
    # Difficulty & mining stats
    BitaxeSensorEntityDescription(
        key="bestDiff",
        translation_key="best_difficulty",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: _parse_difficulty(data.get("bestDiff")),
    ),
    BitaxeSensorEntityDescription(
        key="bestDiff_formatted",
        translation_key="best_difficulty_formatted",
        value_fn=lambda data: _format_difficulty(data.get("bestDiff")),
        exists_fn=lambda data: "bestDiff" in data,
    ),
    _measurement(
        "bestSessionDiff",
        "best_session_difficulty",
        value_fn=lambda data: _parse_difficulty(data.get("bestSessionDiff")),
    ),
    BitaxeSensorEntityDescription(
        key="bestSessionDiff_formatted",
        translation_key="best_session_difficulty_formatted",
        value_fn=lambda data: _format_difficulty(data.get("bestSessionDiff")),
        exists_fn=lambda data: "bestSessionDiff" in data,
    ),
    _measurement("poolDifficulty", "pool_difficulty"),
    _measurement("networkDifficulty", "network_difficulty"),
    BitaxeSensorEntityDescription(
        key="blockHeight",
        translation_key="block_height",
        state_class=SensorStateClass.TOTAL,
    ),
    # Share counters
    BitaxeSensorEntityDescription(
        key="sharesAccepted",
        translation_key="shares_accepted",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BitaxeSensorEntityDescription(
        key="sharesRejected",
        translation_key="shares_rejected",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BitaxeSensorEntityDescription(
        key="blockFound",
        translation_key="blocks_found",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Older firmware reports foundBlocks instead
    BitaxeSensorEntityDescription(
        key="foundBlocks",
        translation_key="blocks_found",
        state_class=SensorStateClass.TOTAL_INCREASING,
        exists_fn=lambda data: "foundBlocks" in data and "blockFound" not in data,
    ),
    BitaxeSensorEntityDescription(
        key="totalFoundBlocks",
        translation_key="total_blocks_found",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Fan & cooling
    _measurement("fanspeed", "fan_speed", native_unit_of_measurement=PERCENTAGE),
    _measurement("fanrpm", "fan_rpm", native_unit_of_measurement="RPM"),
    # AxeOS reports fan2rpm, NerdQAxe fanrpm2/fanspeed2 (zero without a second fan)
    _measurement(
        "fan2rpm",
        "fan_2_rpm",
        native_unit_of_measurement="RPM",
        value_fn=lambda data: data.get("fan2rpm", data.get("fanrpm2")),
        exists_fn=lambda data: "fan2rpm" in data or data.get("fanCount", 0) > 1,
    ),
    _measurement(
        "fanspeed2",
        "fan_2_speed",
        native_unit_of_measurement=PERCENTAGE,
        exists_fn=lambda data: data.get("fanCount", 0) > 1,
    ),
    _measurement(
        "manualFanSpeed",
        "manual_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _measurement(
        "minFanSpeed",
        "minimum_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Network & connectivity
    _measurement(
        "wifiRSSI",
        "wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _measurement(
        "responseTime",
        "pool_response_time",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    _measurement(
        "lastpingrtt",
        "pool_ping",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    _measurement(
        "recentpingloss",
        "pool_ping_loss",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        # Reported as a fraction (0-1)
        value_fn=_scaled("recentpingloss", 100, 1),
    ),
    # System status
    BitaxeSensorEntityDescription(
        key="uptimeSeconds",
        translation_key="uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _measurement(
        "freeHeap",
        "free_memory",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BitaxeSensorEntityDescription(
        key="lastResetReason",
        translation_key="last_reset_reason",
        entity_category=EntityCategory.DIAGNOSTIC,
        # AxeOS reports resetReason as text, NerdQAxe lastResetReason as a UI
        # translation key like SYSTEM.RESET_POWERON
        value_fn=lambda data: (
            str(data["lastResetReason"]).removeprefix("SYSTEM.RESET_")
            if data.get("lastResetReason") is not None
            else data.get("resetReason")
        ),
        exists_fn=lambda data: "lastResetReason" in data or "resetReason" in data,
    ),
    BitaxeSensorEntityDescription(
        key="duplicateHWNonces",
        translation_key="duplicate_hw_nonces",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def _asic_temp(data: dict[str, Any], idx: int) -> Any:
    """Return the temperature of the ASIC at idx from the asicTemps array."""
    temps = data.get("asicTemps", [])
    return temps[idx] if len(temps) > idx else None


def _asic_stat(data: dict[str, Any], idx: int, field: str) -> Any:
    """Return a hashrateMonitor field for the ASIC at idx."""
    asics = data.get("hashrateMonitor", {}).get("asics", [])
    return asics[idx].get(field) if len(asics) > idx else None


def _chip_stat(data: dict[str, Any], idx: int, field: str) -> Any:
    """Return a NerdQAxe dashboard chips field for the ASIC at idx."""
    chips = data.get("chips", [])
    return chips[idx].get(field) if len(chips) > idx else None


def _chip_hashrate(data: dict[str, Any], idx: int) -> Any:
    """Return the total hash rate of the ASIC at idx, including errors."""
    valid = _chip_stat(data, idx, "hashRate")
    errors = _chip_stat(data, idx, "errorHashRate")
    if valid is None:
        return None
    return round(valid + (errors or 0), 2)


def _asic_descriptions(data: dict[str, Any]) -> list[BitaxeSensorEntityDescription]:
    """Return the descriptions of the per-ASIC sensors."""
    descriptions: list[BitaxeSensorEntityDescription] = []

    for i in range(len(data.get("asicTemps", []))):
        descriptions.append(
            _temperature(
                f"asicTemp{i + 1}",
                "asic_n_temperature",
                translation_placeholders={"index": str(i + 1)},
                value_fn=partial(_asic_temp, idx=i),
            )
        )

    # Per-ASIC hash rates come from hashrateMonitor on AxeOS, or from the v2
    # dashboard on NerdQAxe firmware
    if asics := data.get("hashrateMonitor", {}).get("asics", []):
        for i in range(len(asics)):
            placeholders = {"index": str(i + 1)}
            descriptions.append(
                _measurement(
                    f"asic{i + 1}_hashrate",
                    "asic_n_hash_rate",
                    native_unit_of_measurement=HASH_RATE_UNIT,
                    translation_placeholders=placeholders,
                    value_fn=partial(_asic_stat, idx=i, field="total"),
                )
            )
            descriptions.append(
                BitaxeSensorEntityDescription(
                    key=f"asic{i + 1}_errors",
                    translation_key="asic_n_errors",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    translation_placeholders=placeholders,
                    value_fn=partial(_asic_stat, idx=i, field="errorCount"),
                )
            )
    else:
        for i in range(len(data.get("chips", []))):
            placeholders = {"index": str(i + 1)}
            descriptions.append(
                _measurement(
                    f"asic{i + 1}_hashrate",
                    "asic_n_hash_rate",
                    native_unit_of_measurement=HASH_RATE_UNIT,
                    translation_placeholders=placeholders,
                    value_fn=partial(_chip_hashrate, idx=i),
                )
            )
            descriptions.append(
                _measurement(
                    f"asic{i + 1}_error_hashrate",
                    "asic_n_error_hash_rate",
                    native_unit_of_measurement=HASH_RATE_UNIT,
                    translation_placeholders=placeholders,
                    value_fn=partial(_chip_stat, idx=i, field="errorHashRate"),
                )
            )

    return descriptions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bitaxe sensor based on a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.snapshot

    entities: list[SensorEntity] = [
        BitaxeSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if (description.exists_fn(data) if description.exists_fn else description.key in data)
    ]
    entities.extend(
        BitaxeSensor(coordinator, description) for description in _asic_descriptions(data)
    )
    # Integrated energy (kWh) sensor for the Energy Dashboard, derived from power
    if "power" in data:
        entities.append(BitaxeEnergySensor(coordinator))

    async_add_entities(entities)


class BitaxeSensor(BitaxeEntity, SensorEntity):
    """Representation of a Bitaxe sensor."""

    entity_description: BitaxeSensorEntityDescription

    def __init__(
        self,
        coordinator: BitaxeDataUpdateCoordinator,
        description: BitaxeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if (data := self.coordinator.data) is None:
            return None
        if self.entity_description.value_fn is None:
            return data.get(self.entity_description.key)
        return self.entity_description.value_fn(data)


class BitaxeEnergySensor(BitaxeEntity, RestoreSensor):
    """Energy sensor that integrates the power sensor (W) into kWh over time.

    Trapezoidal integration is used so the device can be added to the Home
    Assistant Energy Dashboard without requiring a separate Riemann sum helper.
    """

    _attr_translation_key = "energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: BitaxeDataUpdateCoordinator) -> None:
        """Initialize the energy sensor."""
        super().__init__(coordinator, "energy")
        self._energy_kwh: float = 0.0
        self._last_update: datetime | None = None
        self._last_power: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the accumulated energy value after a restart."""
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_sensor_data()) is not None and isinstance(
            last_data.native_value, (int, float)
        ):
            self._energy_kwh = float(last_data.native_value)
        # Versions before 1.3 only stored the state
        elif (last_state := await self.async_get_last_state()) is not None and (
            last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            try:
                self._energy_kwh = float(last_state.state)
            except ValueError:
                self._energy_kwh = 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Integrate the latest power reading into the running energy total."""
        data = self.coordinator.data
        now = dt_util.utcnow()
        # After a failed update the coordinator keeps stale data; drop the reading
        # so the outage is not integrated as if the miner kept drawing power
        power = data.get("power") if data and self.coordinator.last_update_success else None

        if power is not None and self._last_power is not None and self._last_update is not None:
            elapsed_hours = (now - self._last_update).total_seconds() / 3600
            if elapsed_hours > 0:
                avg_power = (self._last_power + power) / 2
                self._energy_kwh += (avg_power * elapsed_hours) / 1000

        self._last_update = now
        self._last_power = power
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        """Return the accumulated energy in kWh."""
        return round(self._energy_kwh, 3)
