"""Switch platform for Bitaxe integration."""


from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BitaxeApiError
from .const import DOMAIN
from .coordinator import BitaxeConfigEntry, BitaxeDataUpdateCoordinator
from .entity import BitaxeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bitaxe switch entities based on a config entry."""
    coordinator = entry.runtime_data
    # AxeOS supports pause/resume and reports miningPaused. NerdQAxe firmware
    # can only shut down the ASICs (reported as shutdown) and needs a restart
    # to resume mining.
    if "miningPaused" not in coordinator.snapshot and "shutdown" not in coordinator.snapshot:
        return

    async_add_entities([BitaxeMiningSwitch(coordinator)])


class BitaxeMiningSwitch(BitaxeEntity, SwitchEntity):
    """Switch to pause and resume mining."""

    _attr_translation_key = "mining"

    def __init__(self, coordinator: BitaxeDataUpdateCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "mining")

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
                # The device is rebooting; the next regular poll picks up its state
                return
        except BitaxeApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="resume_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause mining, shutting down the ASICs if it cannot pause."""
        try:
            if self._supports_pause:
                await self.coordinator.client.async_pause_mining()
            else:
                await self.coordinator.client.async_shutdown()
        except BitaxeApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="pause_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
