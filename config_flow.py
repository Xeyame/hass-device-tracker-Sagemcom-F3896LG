from __future__ import annotations

import logging
import voluptuous as vol
import aiohttp
import async_timeout

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from .const import DOMAIN, LOGIN_URL

_LOGGER = logging.getLogger(__name__)


async def try_login(host: str, password: str) -> bool:
    """Try to login to the router and return True if successful."""
    url = LOGIN_URL.format(host=host)
    _LOGGER.debug("Attempting login to %s with password %s", url, password)

    connector = aiohttp.TCPConnector(ssl=False)  # ignore self-signed certs

    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with async_timeout.timeout(15):
                async with session.post(url, json={"password": password}) as resp:
                    text = await resp.text()
                    _LOGGER.debug("Login HTTP status: %s", resp.status)
                    _LOGGER.debug("Login response text: %s", text)

                    if resp.status not in (200, 201):
                        return False

                    data = await resp.json()
                    _LOGGER.debug("Login JSON parsed: %s", data)
                    return "created" in data

    except Exception:  # noqa: PERF203
        _LOGGER.exception("Login exception")
        return False


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Router Tracker."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input["host"]
            password = user_input["password"]

            ok = await try_login(host, password)
            if not ok:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Router {host}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )
