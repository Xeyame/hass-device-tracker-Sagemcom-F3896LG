import logging
from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .coordinator import RouterCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the reboot button."""
    coordinator: RouterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RouterRebootButton(coordinator, entry.entry_id)], True)


class RouterRebootButton(ButtonEntity):
    """Button to reboot the router."""

    _attr_name = "Router Reboot"
    _attr_unique_id = "router_reboot"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: RouterCoordinator, entry_id: str):
        super().__init__()
        self.coordinator = coordinator
        self.entry_id = entry_id

    @property
    def device_info(self):
        """Attach this button to the router device."""
        # Must match the router's main device identifiers
        return {
            "identifiers": {(DOMAIN, f"router-{self.entry_id}")},
            "manufacturer": "Router",
            "model": "F3896LG",
            "name": f"Router {self.coordinator.host}",
        }

    async def async_press(self) -> None:
        """Send reboot command to router."""
        url = f"https://{self.coordinator.host}/rest/v1/system/reboot"
        headers = {
            "Authorization": f"Bearer {self.coordinator.token}",
            "Content-Type": "application/json",
        }
        payload = {"reboot": {"enable": True}}

        _LOGGER.warning("Rebooting router at %s", url)

        async with self.coordinator.session.post(url, json=payload, headers=headers) as resp:
            text = await resp.text()

            if resp.status != 202:
                _LOGGER.error("Reboot failed: HTTP %s — %s", resp.status, text)
                raise Exception(f"Reboot failed HTTP {resp.status}")

        _LOGGER.info("Router reboot accepted: %s", text)
