"""Button platform for Bitaxe integration."""


from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
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
    """Set up Bitaxe button entities based on a config entry."""
    async_add_entities([BitaxeRestartButton(entry.runtime_data)])


class BitaxeRestartButton(BitaxeEntity, ButtonEntity):
    """Button to restart the miner."""

    _attr_translation_key = "restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: BitaxeDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "restart")

    async def async_press(self) -> None:
        """Restart the miner."""
        try:
            await self.coordinator.client.async_restart()
        except BitaxeApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="restart_failed",
                translation_placeholders={"error": str(err)},
            ) from err
