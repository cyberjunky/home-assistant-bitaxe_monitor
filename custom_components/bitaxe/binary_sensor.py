"""Binary sensor platform for Bitaxe integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BitaxeDataUpdateCoordinator


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


@dataclass(frozen=True, kw_only=True)
class BitaxeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Bitaxe binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    exists_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[BitaxeBinarySensorEntityDescription, ...] = (
    BitaxeBinarySensorEntityDescription(
        key="pool_connected",
        name="Pool Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        # In dual pool mode all pools must be connected
        value_fn=lambda data: (
            all(pool.get("connected") for pool in _pools(data)) if _pools(data) else None
        ),
        exists_fn=lambda data: any("connected" in pool for pool in _pools(data)),
    ),
    BitaxeBinarySensorEntityDescription(
        key="using_fallback",
        name="Using Fallback Pool",
        icon="mdi:swap-horizontal",
        value_fn=_using_fallback,
        exists_fn=lambda data: _using_fallback(data) is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bitaxe binary sensors based on a config entry."""
    coordinator: BitaxeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}

    async_add_entities(
        BitaxeBinarySensor(coordinator, description, entry)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.exists_fn(data)
    )


class BitaxeBinarySensor(
    CoordinatorEntity[BitaxeDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Bitaxe binary sensor."""

    entity_description: BitaxeBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BitaxeDataUpdateCoordinator,
        description: BitaxeBinarySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
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
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
