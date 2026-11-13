"""Config flow for Bitaxe integration."""


import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import BitaxeApiClient, BitaxeApiError

# Home Assistant 2026.11 replaced voluptuous by the compatible probatio
try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.11
    import voluptuous as vol  # type: ignore[no-redef]
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


def _unique_id(info: dict[str, Any], host: str) -> str:
    """Return the unique ID of a miner, its MAC address when reported."""
    return format_mac(mac) if (mac := info.get("macAddr")) else host


class BitaxeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bitaxe."""

    VERSION = 1

    async def _async_get_info(self, host: str, errors: dict[str, str]) -> dict[str, Any] | None:
        """Return the system info of the miner, or None after setting an error."""
        client = BitaxeApiClient(host, async_get_clientsession(self.hass))
        try:
            return await client.async_get_system_info()
        except BitaxeApiError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            # Entries created before 1.3 are identified by host until set up again
            self._async_abort_entries_match({CONF_HOST: host})
            if (info := await self._async_get_info(host, errors)) is not None:
                await self.async_set_unique_id(_unique_id(info, host))
                # A known miner with a new address only needs its host updated
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=f"Bitaxe {info.get('ASICModel', 'Miner')}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle changing the address of an existing miner."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            if host != entry.data[CONF_HOST]:
                self._async_abort_entries_match({CONF_HOST: host})
            if (info := await self._async_get_info(host, errors)) is not None:
                unique_id = _unique_id(info, host)
                await self.async_set_unique_id(unique_id)
                if entry.unique_id == entry.data[CONF_HOST]:
                    # Identified by its old address, so any miner may take its place
                    if unique_id != entry.unique_id:
                        self._abort_if_unique_id_configured()
                else:
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, data_updates={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )
