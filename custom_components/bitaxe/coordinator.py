"""DataUpdateCoordinator for Bitaxe."""


import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BitaxeApiClient, BitaxeApiError, BitaxeConnectionError
from .const import SCAN_INTERVAL, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

type BitaxeConfigEntry = ConfigEntry[BitaxeDataUpdateCoordinator]


def snapshot_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the store holding the last known data of a miner."""
    return Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")


class BitaxeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Bitaxe data."""

    config_entry: BitaxeConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: BitaxeConfigEntry, client: BitaxeApiClient
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        # Whether the firmware has the v2 dashboard with per-chip hash rates,
        # None until probed
        self._dashboard_supported: bool | None = None
        self._store = snapshot_store(hass, entry.entry_id)
        # Last known data, which decides the entities and device info. Kept in
        # storage so the entities can be set up while the miner is switched off.
        self.snapshot: dict[str, Any] = {}
        self._snapshot_saved = False

    async def async_load_snapshot(self) -> None:
        """Load the last known data from storage."""
        self.snapshot = await self._store.async_load() or {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            data = await self.client.async_get_system_info()
        except BitaxeConnectionError as err:
            # Miners are often switched off, e.g. when power is expensive. Log at
            # info level once, instead of the error the coordinator would log;
            # the coordinator logs at info level again when the miner is back.
            if self.last_update_success:
                _LOGGER.info("%s is unreachable, probably switched off: %s", self.name, err)
                self.last_update_success = False
            raise UpdateFailed(f"Miner is unreachable: {err}") from err
        except BitaxeApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # Only the NerdQAxe firmware fork reports a deviceModel; it exposes
        # per-chip hash rates through the v2 dashboard only
        if "deviceModel" in data and self._dashboard_supported is not False:
            try:
                dashboard = await self.client.async_get_dashboard()
            except BitaxeApiError as err:
                _LOGGER.debug("Error fetching dashboard: %s", err)
            else:
                self._dashboard_supported = dashboard is not None
                if dashboard is not None:
                    data["chips"] = dashboard.get("performance", {}).get("chips", [])

        self._async_update_snapshot(data)
        return data

    def _async_update_snapshot(self, data: dict[str, Any]) -> None:
        """Remember the latest data and keep the device info current."""
        if (version := data.get("version")) != self.snapshot.get("version"):
            device_registry = dr.async_get(self.hass)
            for device in dr.async_entries_for_config_entry(
                device_registry, self.config_entry.entry_id
            ):
                device_registry.async_update_device(device.id, sw_version=version)
            self._snapshot_saved = False

        self.snapshot = data
        # Saving once per run is enough to pick up new or removed values
        if not self._snapshot_saved:
            self._snapshot_saved = True
            self._store.async_delay_save(lambda: self.snapshot, 10)
