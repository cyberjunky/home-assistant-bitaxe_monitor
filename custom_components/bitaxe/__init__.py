"""The Bitaxe integration."""


import logging

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import BitaxeApiClient
from .const import DOMAIN
from .coordinator import BitaxeConfigEntry, BitaxeDataUpdateCoordinator, snapshot_store

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

# Text sensors that moved to the binary sensor platform
REPLACED_SENSORS = ("autofanspeed", "overheat_mode", "overclockEnabled")


async def async_setup_entry(hass: HomeAssistant, entry: BitaxeConfigEntry) -> bool:
    """Set up Bitaxe from a config entry."""
    client = BitaxeApiClient(entry.data[CONF_HOST], async_get_clientsession(hass))
    coordinator = BitaxeDataUpdateCoordinator(hass, entry, client)

    await coordinator.async_load_snapshot()
    if coordinator.snapshot:
        # The entities are known from an earlier run, so set them up even when
        # the miner is switched off; they stay unavailable until it is back
        await coordinator.async_refresh()
    else:
        await coordinator.async_config_entry_first_refresh()

    _async_migrate_unique_id(hass, entry, coordinator)
    _async_remove_replaced_entities(hass, entry, coordinator)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BitaxeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BitaxeConfigEntry) -> None:
    """Remove the stored data of a deleted miner."""
    await snapshot_store(hass, entry.entry_id).async_remove()


@callback
def _async_migrate_unique_id(
    hass: HomeAssistant, entry: BitaxeConfigEntry, coordinator: BitaxeDataUpdateCoordinator
) -> None:
    """Identify entries created before 1.3 by MAC address instead of host."""
    if not (mac := coordinator.snapshot.get("macAddr")):
        return
    unique_id = format_mac(mac)
    if entry.unique_id == unique_id:
        return
    if hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, unique_id):
        _LOGGER.warning("%s has the same MAC address as another configured miner", entry.title)
        return
    hass.config_entries.async_update_entry(entry, unique_id=unique_id)


@callback
def _async_remove_replaced_entities(
    hass: HomeAssistant, entry: BitaxeConfigEntry, coordinator: BitaxeDataUpdateCoordinator
) -> None:
    """Remove entities that were replaced by others."""
    entity_registry = er.async_get(hass)
    replaced = list(REPLACED_SENSORS)
    # Only one of the blocks found sensors is created, the current one wins
    if "blockFound" in coordinator.snapshot:
        replaced.append("foundBlocks")
    for key in replaced:
        if entity_id := entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{entry.entry_id}_{key}"
        ):
            entity_registry.async_remove(entity_id)
