"""Binary sensor platform for Bitaxe integration."""


from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BitaxeConfigEntry, BitaxeDataUpdateCoordinator
from .entity import BitaxeEntity


def _pools(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the pools reported by NerdQAxe firmware."""
    stratum = data.get("stratum")
    return stratum.get("pools", []) if isinstance(stratum, dict) else []


def _using_fallback(data: dict[str, Any]) -> bool | None:
    """Return true if mining on the fallback pool."""
    if "isUsingFallbackStratum" in data:
        return bool(data["isUsingFallbackStratum"])
    stratum = data.get("stratum")
    if isinstance(stratum, dict) and "usingFallback" in stratum:
        return bool(stratum["usingFallback"])
    return None


def _flag(key: str) -> Callable[[dict[str, Any]], bool | None]:
    """Return a value function for a boolean or 0/1 API value."""
    return lambda data: bool(data[key]) if data.get(key) is not None else None


@dataclass(frozen=True, kw_only=True)
class BitaxeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Bitaxe binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    # Defaults to the entity key being in the data
    exists_fn: Callable[[dict[str, Any]], bool] | None = None


BINARY_SENSOR_DESCRIPTIONS: tuple[BitaxeBinarySensorEntityDescription, ...] = (
    BitaxeBinarySensorEntityDescription(
        key="pool_connected",
        translation_key="pool_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        # In dual pool mode all pools must be connected
        value_fn=lambda data: (
            all(pool.get("connected") for pool in _pools(data)) if _pools(data) else None
        ),
        exists_fn=lambda data: any("connected" in pool for pool in _pools(data)),
    ),
    BitaxeBinarySensorEntityDescription(
        key="using_fallback",
        translation_key="using_fallback",
        value_fn=_using_fallback,
        exists_fn=lambda data: _using_fallback(data) is not None,
    ),
    BitaxeBinarySensorEntityDescription(
        key="overheat_mode",
        translation_key="overheat",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_flag("overheat_mode"),
    ),
    BitaxeBinarySensorEntityDescription(
        key="autofanspeed",
        translation_key="auto_fan_speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("autofanspeed"),
    ),
    BitaxeBinarySensorEntityDescription(
        key="overclockEnabled",
        translation_key="overclock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("overclockEnabled"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bitaxe binary sensors based on a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.snapshot

    async_add_entities(
        BitaxeBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if (description.exists_fn(data) if description.exists_fn else description.key in data)
    )


class BitaxeBinarySensor(BitaxeEntity, BinarySensorEntity):
    """Representation of a Bitaxe binary sensor."""

    entity_description: BitaxeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: BitaxeDataUpdateCoordinator,
        description: BitaxeBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if (data := self.coordinator.data) is None:
            return None
        return self.entity_description.value_fn(data)
