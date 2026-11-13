"""Base entity for the Bitaxe integration."""


from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BitaxeDataUpdateCoordinator


class BitaxeEntity(CoordinatorEntity[BitaxeDataUpdateCoordinator]):
    """Base class for Bitaxe entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BitaxeDataUpdateCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        info = coordinator.snapshot
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            connections=(
                {(CONNECTION_NETWORK_MAC, format_mac(mac))}
                if (mac := info.get("macAddr"))
                else set()
            ),
            name=entry.title,
            manufacturer="Bitaxe",
            model=info.get("ASICModel"),
            sw_version=info.get("version"),
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
