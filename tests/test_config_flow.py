"""Tests for the Bitaxe config flow."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.bitaxe.const import DOMAIN

from .conftest import HOST, INFO_URL, axeos_info

NEW_HOST = "192.168.1.101"


@pytest.fixture(autouse=True)
async def mock_setup_entry(hass: HomeAssistant) -> AsyncGenerator[AsyncMock]:
    """Prevent created entries from actually being set up."""
    with (
        patch("custom_components.bitaxe.async_setup_entry", AsyncMock(return_value=True)) as mock,
        patch("custom_components.bitaxe.async_unload_entry", AsyncMock(return_value=True)),
    ):
        yield mock
        # Unload while patched; the real unload expects state the mock never set up
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_unload(entry.entry_id)


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A reachable miner is added and named after its ASIC model."""
    aioclient_mock.get(INFO_URL, json=axeos_info())

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bitaxe BM1370"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == HOST


@pytest.mark.parametrize(
    "mock_kwargs",
    [
        {"exc": aiohttp.ClientConnectionError()},
        {"exc": aiohttp.ClientError()},
        {"exc": TimeoutError()},
        {"status": 404},
        {"text": "<html>captive portal</html>"},
    ],
)
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_kwargs: dict
) -> None:
    """Connection problems show cannot_connect and allow a retry."""
    aioclient_mock.get(INFO_URL, **mock_kwargs)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=axeos_info())
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A non-object JSON response is reported as an unknown error."""
    aioclient_mock.get(INFO_URL, json=[1, 2, 3])

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The same host cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.get(INFO_URL, json=axeos_info())

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_success(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The miner address can be changed, moving the unique ID along."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.get(f"http://{NEW_HOST}/api/system/info", json=axeos_info())

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_HOST: NEW_HOST}
    assert mock_config_entry.unique_id == NEW_HOST


async def test_reconfigure_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An unreachable new address keeps the form open."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.get(f"http://{NEW_HOST}/api/system/info", exc=aiohttp.ClientConnectionError())

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_config_entry.data == {CONF_HOST: HOST}


async def test_reconfigure_to_other_configured_miner(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reconfiguring onto the address of another entry aborts."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: NEW_HOST}, unique_id=NEW_HOST).add_to_hass(hass)
    aioclient_mock.get(f"http://{NEW_HOST}/api/system/info", json=axeos_info())

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: HOST}


async def test_reconfigure_same_host(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Re-entering the current address succeeds."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.get(INFO_URL, json=axeos_info())

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
