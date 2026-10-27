"""Button platform for Bitaxe integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BitaxeApiError
from .const import DOMAIN
from .coordinator import BitaxeDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bitaxe button entities based on a config entry."""
    coordinator: BitaxeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BitaxeRestartButton(coordinator, entry)])


class BitaxeRestartButton(CoordinatorEntity[BitaxeDataUpdateCoordinator], ButtonEntity):
    """Button to restart the miner."""

    _attr_has_entity_name = True
    _attr_name = "Restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: BitaxeDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_restart"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Bitaxe",
            "model": coordinator.data.get("ASICModel", "Unknown"),
            "sw_version": coordinator.data.get("version", "Unknown"),
        }

    async def async_press(self) -> None:
        """Restart the miner."""
        try:
            await self.coordinator.client.async_restart()
        except BitaxeApiError as err:
            raise HomeAssistantError(f"Failed to restart: {err}") from err
