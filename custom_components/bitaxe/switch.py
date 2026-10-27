"""Switch platform for Bitaxe integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Bitaxe switch entities based on a config entry."""
    coordinator: BitaxeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    # AxeOS supports pause/resume and reports miningPaused. NerdQAxe firmware
    # can only shut down the ASICs (reported as shutdown) and needs a restart
    # to resume mining.
    if "miningPaused" not in data and "shutdown" not in data:
        return

    async_add_entities([BitaxeMiningSwitch(coordinator, entry)])


class BitaxeMiningSwitch(CoordinatorEntity[BitaxeDataUpdateCoordinator], SwitchEntity):
    """Switch to pause and resume mining."""

    _attr_has_entity_name = True
    _attr_name = "Mining"
    _attr_icon = "mdi:pickaxe"

    def __init__(
        self, coordinator: BitaxeDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_mining"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Bitaxe",
            "model": coordinator.data.get("ASICModel", "Unknown"),
            "sw_version": coordinator.data.get("version", "Unknown"),
        }

    @property
    def _supports_pause(self) -> bool:
        """Return true if the firmware supports pausing and resuming."""
        return "miningPaused" in (self.coordinator.data or {})

    @property
    def is_on(self) -> bool | None:
        """Return true if the miner is mining."""
        data = self.coordinator.data or {}
        paused = data.get("miningPaused", data.get("shutdown"))
        if paused is None:
            return None
        return not paused

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Resume mining, restarting the device if it cannot resume in place."""
        try:
            if self._supports_pause:
                await self.coordinator.client.async_resume_mining()
            else:
                await self.coordinator.client.async_restart()
        except BitaxeApiError as err:
            raise HomeAssistantError(f"Failed to resume mining: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause mining, shutting down the ASICs if it cannot pause."""
        try:
            if self._supports_pause:
                await self.coordinator.client.async_pause_mining()
            else:
                await self.coordinator.client.async_shutdown()
        except BitaxeApiError as err:
            raise HomeAssistantError(f"Failed to pause mining: {err}") from err
        await self.coordinator.async_request_refresh()
