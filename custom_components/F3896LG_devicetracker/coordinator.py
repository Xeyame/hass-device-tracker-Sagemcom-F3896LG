from __future__ import annotations

import logging
from datetime import timedelta
import aiohttp

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import LOGIN_URL, HOSTS_URL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RouterCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch router data + dynamically announce new devices."""

    def __init__(self, hass: HomeAssistant, host: str, password: str):
        self.hass = hass
        self.host = host
        self.password = password

        # Tracks which MACs already created device_tracker entities
        self.known_macs: set[str] = set()

        # HTTP session
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        )

        self.token: str | None = None
        self._login_attempted = False

        super().__init__(
            hass,
            _LOGGER,
            name="F3896LG_devicetracker",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_login(self):
        """Authenticate to the router."""
        url = LOGIN_URL.format(host=self.host)

        try:
            async with self.session.post(url, json={"password": self.password}) as resp:
                data = await resp.json()

                if resp.status not in (200, 201):
                    raise UpdateFailed(f"Login HTTP {resp.status}")

                self.token = data["created"]["token"]
                self._login_attempted = True

        except Exception as e:
            self.token = None
            raise UpdateFailed(f"Login failed: {e}")

    async def _async_update_data(self):
        """Fetch and normalize host data, detect new devices."""
        if not self._login_attempted or not self.token:
            await self._async_login()

        url = HOSTS_URL.format(host=self.host)
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            async with self.session.get(url, headers=headers) as resp:
                text = await resp.text()
                _LOGGER.debug(
                    "RouterTracker RAW HOST RESPONSE (status %s): %s",
                    resp.status,
                    text[:5000],
                )

                try:
                    data = await resp.json()
                except Exception as e:
                    raise UpdateFailed(f"Router returned non-JSON response: {e}")

                # Token expired
                if resp.status == 401:
                    self.token = None
                    await self._async_login()
                    return await self._async_update_data()

                if resp.status != 200:
                    raise UpdateFailed(f"Host fetch HTTP {resp.status}")

                raw_hosts = data.get("hosts", {}).get("hosts", [])

                hosts = []
                newly_discovered = []

                for h in raw_hosts:
                    mac = h.get("macAddress")
                    if not mac:
                        _LOGGER.error("Skipping host without macAddress: %s", h)
                        continue

                    mac = mac.lower()

                    cfg = h.get("config", {})
                    wifi = cfg.get("wifi", {})

                    host = {
                        "mac": mac,
                        "hostname": cfg.get("hostname") or "",
                        "connected": cfg.get("connected", False),
                        "ip": cfg.get("ipv4", {}).get("address"),
                        "interface": cfg.get("interface"),
                        "device_type": cfg.get("deviceType"),
                        "wifi": wifi,
                        "rssi": wifi.get("rssi"),
                        "raw": h,
                    }

                    hosts.append(host)

                    # ?? Notify about new devices
                    if mac not in self.known_macs:
                        newly_discovered.append(host)
                        self.known_macs.add(mac)

                # ?? Announce new devices to device_tracker.py
                for host in newly_discovered:
                    _LOGGER.info("Discovered NEW router client: %s", host["mac"])
                    async_dispatcher_send(
                        self.hass,
                        f"{DOMAIN}_new_device",
                        host,
                    )

                return {"hosts": hosts}

        except Exception as e:
            raise UpdateFailed(f"Host fetch failed: {e}")
