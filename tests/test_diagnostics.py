"""Tests for Bitaxe diagnostics."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.bitaxe.diagnostics import async_get_config_entry_diagnostics

from .conftest import mock_api


async def test_diagnostics_redacted(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Diagnostics contain the miner data without addresses or wallet."""
    mock_api(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["last_update_success"] is True
    assert diagnostics["data"]["hashRate"] == 1000.5
    assert diagnostics["data"]["macAddr"] == "**REDACTED**"
    assert diagnostics["data"]["stratumUser"] == "**REDACTED**"
    assert diagnostics["snapshot"]["stratumUser"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
    assert diagnostics["entry"]["unique_id"] == "**REDACTED**"
