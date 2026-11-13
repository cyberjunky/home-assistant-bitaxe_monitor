"""Diagnostics support for Bitaxe."""


from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import BitaxeConfigEntry

# Wallet addresses, credentials and network identifiers, also inside nested pools
TO_REDACT = {
    CONF_HOST,
    "macAddr",
    "ssid",
    "hostname",
    "ipv4",
    "ipv6",
    "stratumUser",
    "stratumPassword",
    "fallbackStratumUser",
    "fallbackStratumPassword",
    "user",
    "password",
    "pass",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BitaxeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT | {"unique_id"}),
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
        "snapshot": async_redact_data(coordinator.snapshot, TO_REDACT),
    }
