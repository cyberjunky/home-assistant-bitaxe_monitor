"""Tests for Bitaxe setup and unload."""

import logging
from datetime import timedelta
from typing import Any

import aiohttp
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.bitaxe.const import DOMAIN, SCAN_INTERVAL, STORAGE_KEY

from .conftest import (
    DASHBOARD_URL,
    HOST,
    INFO_URL,
    MAC,
    axeos_info,
    mock_api,
    nerdqaxe_dashboard,
    nerdqaxe_info,
    store_snapshot,
)


async def test_setup_and_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The entry sets up, stores its coordinator and unloads cleanly."""
    mock_api(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_unreachable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A miner that was never reached puts the entry in setup retry."""
    aioclient_mock.get(INFO_URL, exc=aiohttp.ClientConnectionError())
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_while_switched_off(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A miner seen before sets up from its last known data while switched off."""
    store_snapshot(hass_storage, mock_config_entry, axeos_info())
    # The first registered response wins, the rest mocks the firmware releases
    aioclient_mock.get(INFO_URL, exc=aiohttp.ClientConnectionError())
    mock_api(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    with caplog.at_level(logging.INFO, logger="custom_components.bitaxe"):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    power = _entity_id(hass, mock_config_entry, "sensor", "power")
    assert power is not None
    assert hass.states.is_state(power, STATE_UNAVAILABLE)
    assert "is unreachable, probably switched off" in caplog.text
    assert not _problems(caplog)

    # The miner is switched on again
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.is_state(power, "15.2")


async def test_switched_off_while_running(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Switching a miner off is logged once at info level, other errors as error."""
    mock_api(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    coordinator = mock_config_entry.runtime_data

    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, exc=TimeoutError())
    with caplog.at_level(logging.INFO, logger="custom_components.bitaxe"):
        await coordinator.async_refresh()
        await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert caplog.text.count("is unreachable, probably switched off") == 1
    assert not _problems(caplog)

    # A miner that answers with an error is not switched off
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock)
    await coordinator.async_refresh()
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, status=500)
    caplog.clear()
    await coordinator.async_refresh()

    assert [r.levelno for r in caplog.records if "HTTP 500" in r.getMessage()] == [logging.ERROR]


async def test_snapshot_saved_and_removed(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The last known data is stored, and removed with the entry."""
    mock_api(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    key = f"{STORAGE_KEY}.{mock_config_entry.entry_id}"
    assert hass_storage[key]["data"]["ASICModel"] == "BM1370"

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_unique_id_migrated_to_mac(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Entries identified by host are identified by MAC address after setup."""
    mock_api(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.unique_id == MAC
    device = _device(hass, mock_config_entry)
    assert (dr.CONNECTION_NETWORK_MAC, MAC) in device.connections


async def test_unique_id_not_migrated_when_taken(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The unique ID is kept if another entry already has the MAC address."""
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.200"}, unique_id=MAC).add_to_hass(
        hass
    )
    mock_api(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.unique_id == HOST


async def test_replaced_entities_removed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Text sensors replaced by binary sensors are removed from the registry."""
    mock_config_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    for key in ("autofanspeed", "foundBlocks"):
        entity_registry.async_get_or_create(
            "sensor", DOMAIN, f"{mock_config_entry.entry_id}_{key}", config_entry=mock_config_entry
        )
    mock_api(aioclient_mock)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for key in ("autofanspeed", "foundBlocks"):
        assert _entity_id(hass, mock_config_entry, "sensor", key) is None
    assert _entity_id(hass, mock_config_entry, "binary_sensor", "autofanspeed") is not None


async def test_firmware_version_updates_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The device shows the new firmware version after an upgrade."""
    mock_api(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    mock_api(aioclient_mock, axeos_info() | {"version": "v2.6.0"})
    await mock_config_entry.runtime_data.async_refresh()

    device = _device(hass, mock_config_entry)
    assert device.sw_version == "v2.6.0"


async def test_dashboard_error_is_retried(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A temporary dashboard error does not disable the per-chip sensors."""
    mock_api(aioclient_mock, nerdqaxe_info())
    aioclient_mock.get(DASHBOARD_URL, status=500)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    coordinator = mock_config_entry.runtime_data
    assert "chips" not in coordinator.data

    aioclient_mock.clear_requests()
    mock_api(aioclient_mock, nerdqaxe_info(), dashboard=nerdqaxe_dashboard())
    await coordinator.async_refresh()

    assert len(coordinator.data["chips"]) == 2


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")


def _device(hass: HomeAssistant, entry: MockConfigEntry) -> dr.DeviceEntry:
    registry = dr.async_get(hass)
    [device] = dr.async_entries_for_config_entry(registry, entry.entry_id)
    return device


def _problems(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the warnings and errors logged by the integration."""
    return [
        record
        for record in caplog.records
        if record.name.startswith("custom_components.bitaxe") and record.levelno >= logging.WARNING
    ]
