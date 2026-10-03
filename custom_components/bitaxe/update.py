"""Update platform for Bitaxe integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .coordinator import BitaxeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

FIRMWARE_SCAN_INTERVAL = timedelta(hours=6)

# GitHub repositories publishing the firmware releases
FIRMWARE_REPO_ESP_MINER = "bitaxeorg/ESP-Miner"
FIRMWARE_REPO_NERDQAXE = "shufps/ESP-Miner-NerdQAxePlus"

# hass.data key holding one release coordinator per repository, shared by all miners
DATA_FIRMWARE = f"{DOMAIN}_firmware"


def _firmware_repo(data: dict[str, Any]) -> str:
    """Return the firmware repository matching the device."""
    # Only the NerdQAxe firmware fork reports a deviceModel
    if "deviceModel" in data:
        return FIRMWARE_REPO_NERDQAXE
    return FIRMWARE_REPO_ESP_MINER


class BitaxeFirmwareCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to fetch the latest firmware release from GitHub."""

    def __init__(self, hass: HomeAssistant, repo: str) -> None:
        """Initialize."""
        self.repo = repo
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=f"{DOMAIN} firmware {repo}",
            update_interval=FIRMWARE_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest stable release."""
        session = async_get_clientsession(self.hass)
        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        try:
            async with session.get(
                url,
                headers={"Accept": "application/vnd.github+json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                data = await response.json()
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise UpdateFailed(f"Error fetching {self.repo} release: {err}") from err
        if not isinstance(data, dict) or not data.get("tag_name"):
            raise UpdateFailed(f"Unexpected release data for {self.repo}")
        return data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bitaxe update entity based on a config entry."""
    coordinator: BitaxeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if "version" not in (coordinator.data or {}):
        return

    repo = _firmware_repo(coordinator.data)
    firmware_coordinators = hass.data.setdefault(DATA_FIRMWARE, {})
    if (firmware := firmware_coordinators.get(repo)) is None:
        firmware = firmware_coordinators[repo] = BitaxeFirmwareCoordinator(hass, repo)
        # A GitHub outage must not block setup; the entity stays unknown until it recovers
        await firmware.async_refresh()

    async_add_entities([BitaxeFirmwareUpdate(coordinator, firmware, entry)])


class BitaxeFirmwareUpdate(
    CoordinatorEntity[BitaxeDataUpdateCoordinator], UpdateEntity
):
    """Firmware update entity, informational only (install through AxeOS)."""

    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: BitaxeDataUpdateCoordinator,
        firmware: BitaxeFirmwareCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self._firmware = firmware
        self._attr_unique_id = f"{entry.entry_id}_firmware"
        self._attr_title = firmware.repo.split("/")[1]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Bitaxe",
            "model": coordinator.data.get("ASICModel", "Unknown"),
            "sw_version": coordinator.data.get("version", "Unknown"),
        }

    async def async_added_to_hass(self) -> None:
        """Also refresh the state when a new release is fetched."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._firmware.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def installed_version(self) -> str | None:
        """Return the firmware version running on the miner."""
        return (self.coordinator.data or {}).get("version")

    @property
    def latest_version(self) -> str | None:
        """Return the latest released firmware version."""
        return (self._firmware.data or {}).get("tag_name")

    @property
    def release_url(self) -> str | None:
        """Return the URL of the latest release."""
        return (self._firmware.data or {}).get("html_url")

    async def async_release_notes(self) -> str | None:
        """Return the release notes of the latest release."""
        return (self._firmware.data or {}).get("body")
