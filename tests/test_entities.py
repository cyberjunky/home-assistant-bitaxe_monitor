"""Tests for the Bitaxe entity platforms."""

from datetime import timedelta

import aiohttp
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry, mock_restore_cache
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.bitaxe.const import DOMAIN
from custom_components.bitaxe.update import FIRMWARE_REPO_ESP_MINER

from .conftest import (
    BASE_URL,
    INFO_URL,
    mock_api,
    nerdqaxe_dashboard,
    nerdqaxe_info,
    release_url,
)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")


def _state(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> State:
    entity_id = _entity_id(hass, entry, platform, key)
    assert entity_id is not None, key
    state = hass.states.get(entity_id)
    assert state is not None, key
    return state


async def test_axeos_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors are created for reported keys and convert their values."""
    mock_api(aioclient_mock)
    await _setup(hass, mock_config_entry)

    def value(key: str) -> str:
        return _state(hass, mock_config_entry, "sensor", key).state

    assert value("power") == "15.2"
    assert value("current") == "3.0"
    assert value("hashRate") == "1000.5"
    assert float(value("efficiency")) == round(15.2 / (1000.5 / 1000), 2)
    assert float(value("bestDiff")) == 4.29e9
    assert value("bestDiff_formatted") == "4.29G"
    assert float(value("bestSessionDiff")) == 123456
    assert value("bestSessionDiff_formatted") == "123.46k"
    assert value("asicTemp1") == "52.0"
    assert value("asicTemp2") == "53.5"
    assert value("asic1_hashrate") == "500.25"
    assert value("asic1_errors") == "2"
    assert value("energy") == "0.0"

    assert value("blockFound") == "0"

    # Keys the miner does not report are not created
    assert _entity_id(hass, mock_config_entry, "sensor", "temp2") is None
    assert _entity_id(hass, mock_config_entry, "sensor", "fan2rpm") is None
    # Only one blocks found sensor when the firmware reports both keys
    assert _entity_id(hass, mock_config_entry, "sensor", "foundBlocks") is None

    # Names come from the translations
    asic_temp = _state(hass, mock_config_entry, "sensor", "asicTemp2")
    assert asic_temp.attributes["friendly_name"] == "Bitaxe BM1370 ASIC 2 Temperature"


async def test_current_zero(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A current of 0 mA is reported as 0 A, not unknown."""
    mock_api(aioclient_mock, {"power": 0.0, "current": 0})
    await _setup(hass, mock_config_entry)

    assert _state(hass, mock_config_entry, "sensor", "current").state == "0.0"


async def test_axeos_binary_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """AxeOS reports only the fallback flag, not pool connectivity."""
    mock_api(aioclient_mock)
    await _setup(hass, mock_config_entry)

    assert _state(hass, mock_config_entry, "binary_sensor", "using_fallback").state == STATE_OFF
    assert _state(hass, mock_config_entry, "binary_sensor", "autofanspeed").state == STATE_ON
    assert _state(hass, mock_config_entry, "binary_sensor", "overheat_mode").state == STATE_OFF
    assert _entity_id(hass, mock_config_entry, "binary_sensor", "pool_connected") is None
    assert _entity_id(hass, mock_config_entry, "binary_sensor", "overclockEnabled") is None


async def test_axeos_mining_switch(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The mining switch pauses and resumes AxeOS miners."""
    mock_api(aioclient_mock)
    aioclient_mock.post(f"{BASE_URL}/api/system/pause")
    aioclient_mock.post(f"{BASE_URL}/api/system/resume")
    await _setup(hass, mock_config_entry)

    entity_id = _state(hass, mock_config_entry, "switch", "mining").entity_id
    assert hass.states.is_state(entity_id, STATE_ON)

    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True)

    posted = [str(url) for method, url, _, _ in aioclient_mock.mock_calls if method == "POST"]
    assert posted == [f"{BASE_URL}/api/system/pause", f"{BASE_URL}/api/system/resume"]


async def test_mining_switch_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failing command raises a Home Assistant error."""
    mock_api(aioclient_mock)
    aioclient_mock.post(f"{BASE_URL}/api/system/pause", exc=aiohttp.ClientConnectionError())
    await _setup(hass, mock_config_entry)

    entity_id = _entity_id(hass, mock_config_entry, "switch", "mining")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )


async def test_restart_button(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The restart button posts to the restart endpoint."""
    mock_api(aioclient_mock)
    aioclient_mock.post(f"{BASE_URL}/api/system/restart")
    await _setup(hass, mock_config_entry)

    entity_id = _entity_id(hass, mock_config_entry, "button", "restart")
    await hass.services.async_call("button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True)

    assert any(
        method == "POST" and str(url).endswith("/api/system/restart")
        for method, url, _, _ in aioclient_mock.mock_calls
    )


async def test_restart_button_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failing restart raises a Home Assistant error."""
    mock_api(aioclient_mock)
    aioclient_mock.post(f"{BASE_URL}/api/system/restart", status=500)
    await _setup(hass, mock_config_entry)

    entity_id = _entity_id(hass, mock_config_entry, "button", "restart")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )


async def test_firmware_update_entity(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The update entity compares the running and latest ESP-Miner release."""
    mock_api(aioclient_mock)
    await _setup(hass, mock_config_entry)

    state = _state(hass, mock_config_entry, "update", "firmware")
    assert state.state == STATE_ON
    assert state.attributes["installed_version"] == "v2.5.0"
    assert state.attributes["latest_version"] == "v2.6.0"
    assert state.attributes["title"] == "ESP-Miner"
    assert state.attributes["release_url"].endswith("/releases/tag/v2.6.0")


async def test_firmware_update_github_down(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A GitHub outage does not block setup."""
    aioclient_mock.get(release_url(FIRMWARE_REPO_ESP_MINER), status=503)
    mock_api(aioclient_mock)
    await _setup(hass, mock_config_entry)

    state = _state(hass, mock_config_entry, "update", "firmware")
    assert state.attributes["installed_version"] == "v2.5.0"
    assert state.attributes["latest_version"] is None


async def test_nerdqaxe_entities(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """NerdQAxe miners get per-chip sensors, pool status and shutdown control."""
    mock_api(aioclient_mock, nerdqaxe_info(), dashboard=nerdqaxe_dashboard())
    aioclient_mock.post(f"{BASE_URL}/api/system/shutdown")
    aioclient_mock.post(f"{BASE_URL}/api/system/restart")
    await _setup(hass, mock_config_entry)

    assert _state(hass, mock_config_entry, "sensor", "asic1_hashrate").state == "1205.5"
    assert _state(hass, mock_config_entry, "sensor", "asic1_error_hashrate").state == "5.5"
    assert _state(hass, mock_config_entry, "sensor", "asic2_hashrate").state == "1190.0"

    # Not all pools connected in dual pool mode
    assert _state(hass, mock_config_entry, "binary_sensor", "pool_connected").state == STATE_OFF
    assert _state(hass, mock_config_entry, "binary_sensor", "using_fallback").state == STATE_ON

    update = _state(hass, mock_config_entry, "update", "firmware")
    assert update.attributes["title"] == "ESP-Miner-NerdQAxePlus"
    assert update.attributes["latest_version"] == "v1.0.31"

    # Without pause support the switch shuts down the ASICs and restarts to resume
    entity_id = _state(hass, mock_config_entry, "switch", "mining").entity_id
    assert hass.states.is_state(entity_id, STATE_ON)
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    posted = [str(url) for method, url, _, _ in aioclient_mock.mock_calls if method == "POST"]
    assert posted == [f"{BASE_URL}/api/system/shutdown", f"{BASE_URL}/api/system/restart"]


async def test_nerdqaxe_without_dashboard(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Older NerdQAxe firmware without the v2 dashboard has no per-chip sensors."""
    mock_api(aioclient_mock, nerdqaxe_info())
    aioclient_mock.get(f"{BASE_URL}/api/v2/dashboard", status=302)
    await _setup(hass, mock_config_entry)

    assert _entity_id(hass, mock_config_entry, "sensor", "asic1_hashrate") is None
    assert _state(hass, mock_config_entry, "sensor", "power").state == "80.0"


async def test_no_switch_or_update_without_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Miners without pause state or version get no switch and update entity."""
    mock_api(aioclient_mock, {"power": 10.0, "hashRate": 0})
    await _setup(hass, mock_config_entry)

    assert _entity_id(hass, mock_config_entry, "switch", "mining") is None
    assert _entity_id(hass, mock_config_entry, "update", "firmware") is None
    # Efficiency is unknown without a hash rate
    assert _state(hass, mock_config_entry, "sensor", "efficiency").state == STATE_UNKNOWN


async def test_energy_sensor_integrates_power(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The energy sensor integrates power over time and skips failed updates."""
    mock_api(aioclient_mock, {"power": 20.0})
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # The first reading only sets the baseline
    await coordinator.async_refresh()
    freezer.tick(timedelta(hours=1))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, mock_config_entry, "sensor", "energy").state == "0.02"

    # A failed update resets the baseline instead of integrating the outage
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, exc=aiohttp.ClientConnectionError())
    freezer.tick(timedelta(hours=1))
    await coordinator.async_refresh()
    aioclient_mock.clear_requests()
    mock_api(aioclient_mock, {"power": 20.0})
    freezer.tick(timedelta(hours=1))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, mock_config_entry, "sensor", "energy").state == "0.02"


async def test_energy_sensor_restores_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The accumulated energy survives a restart."""
    mock_config_entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{mock_config_entry.entry_id}_energy",
        config_entry=mock_config_entry,
        suggested_object_id="bitaxe_energy",
    )
    mock_restore_cache(hass, [State("sensor.bitaxe_energy", "1.234")])
    mock_api(aioclient_mock)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.is_state("sensor.bitaxe_energy", "1.234")
