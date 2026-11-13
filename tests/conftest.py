"""Fixtures for Bitaxe tests."""

from collections.abc import Generator
from typing import Any

import pytest
from homeassistant.const import CONF_HOST
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.bitaxe.const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from custom_components.bitaxe.update import (
    DATA_FIRMWARE,
    FIRMWARE_REPO_ESP_MINER,
    FIRMWARE_REPO_NERDQAXE,
)

HOST = "192.168.1.100"
MAC = "aa:bb:cc:dd:ee:ff"
BASE_URL = f"http://{HOST}"
INFO_URL = f"{BASE_URL}/api/system/info"
DASHBOARD_URL = f"{BASE_URL}/api/v2/dashboard"


def release_url(repo: str) -> str:
    """Return the GitHub latest release API URL for a repository."""
    return f"https://api.github.com/repos/{repo}/releases/latest"


def axeos_info() -> dict[str, Any]:
    """Return /api/system/info output of a stock AxeOS miner."""
    return {
        "ASICModel": "BM1370",
        "version": "v2.5.0",
        "macAddr": "AA:BB:CC:DD:EE:FF",
        "stratumUser": "bc1qwallet.worker",
        "power": 15.2,
        "voltage": 5100,
        "current": 3000,
        "temp": 55.5,
        "vrTemp": 48,
        "hashRate": 1000.5,
        "bestDiff": "4.29G",
        "bestSessionDiff": 123456,
        "sharesAccepted": 1200,
        "sharesRejected": 3,
        "frequency": 525,
        "fanspeed": 80,
        "fanrpm": 4200,
        "autofanspeed": 1,
        "overheat_mode": 0,
        "blockFound": 0,
        "foundBlocks": 0,
        "uptimeSeconds": 3600,
        "miningPaused": False,
        "isUsingFallbackStratum": 0,
        "asicTemps": [52.0, 53.5],
        "hashrateMonitor": {"asics": [{"total": 500.25, "errorCount": 2}]},
    }


def nerdqaxe_info() -> dict[str, Any]:
    """Return /api/system/info output of a NerdQAxe miner."""
    return {
        "ASICModel": "BM1370",
        "deviceModel": "NerdQAxe++",
        "version": "v1.0.30",
        "power": 80.0,
        "hashRate": 4800.0,
        "shutdown": False,
        "stratum": {
            "usingFallback": True,
            "pools": [{"connected": True}, {"connected": False}],
        },
    }


def nerdqaxe_dashboard() -> dict[str, Any]:
    """Return the NerdQAxe v2 dashboard output."""
    return {
        "performance": {
            "chips": [
                {"hashRate": 1200.0, "errorHashRate": 5.5},
                {"hashRate": 1190.0, "errorHashRate": 0},
            ]
        }
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of the custom integration in all tests."""
    return


@pytest.fixture(autouse=True)
def clear_firmware_coordinators(hass) -> Generator[None]:
    """The firmware coordinators live in hass.data outside any entry."""
    yield
    hass.data.pop(DATA_FIRMWARE, None)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry, identified by host like before 1.3."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Bitaxe BM1370",
        data={CONF_HOST: HOST},
        unique_id=HOST,
    )


def store_snapshot(
    hass_storage: dict[str, Any], entry: MockConfigEntry, data: dict[str, Any]
) -> None:
    """Store the last known data of a miner, as saved by an earlier run."""
    key = f"{STORAGE_KEY}.{entry.entry_id}"
    hass_storage[key] = {"version": STORAGE_VERSION, "minor_version": 1, "key": key, "data": data}


def mock_api(
    aioclient_mock: AiohttpClientMocker,
    info: dict[str, Any] | None = None,
    *,
    dashboard: dict[str, Any] | None = None,
) -> None:
    """Register the miner and GitHub responses."""
    aioclient_mock.get(INFO_URL, json=axeos_info() if info is None else info)
    if dashboard is not None:
        aioclient_mock.get(
            DASHBOARD_URL, json=dashboard, headers={"Content-Type": "application/json"}
        )
    for repo, tag in ((FIRMWARE_REPO_ESP_MINER, "v2.6.0"), (FIRMWARE_REPO_NERDQAXE, "v1.0.31")):
        aioclient_mock.get(
            release_url(repo),
            json={
                "tag_name": tag,
                "html_url": f"https://github.com/{repo}/releases/tag/{tag}",
                "body": "Release notes",
            },
        )
