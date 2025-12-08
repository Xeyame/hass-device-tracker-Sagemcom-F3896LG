import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import device_registry as dr

from .coordinator import RouterCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN = "router_tracker"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the router_tracker component."""
    _LOGGER.debug("router_tracker async_setup called")
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up router_tracker from a config entry."""
    _LOGGER.debug("Setting up entry %s for router_tracker", entry.title)

    coordinator = RouterCoordinator(
        hass,
        host=entry.data["host"],
        password=entry.data["password"],
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    #
    # ?? Create router device in registry (parent device)
    #
    dev_reg = dr.async_get(hass)

    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"router-{entry.entry_id}")},
        manufacturer="Router Tracker",
        name=f"Router {entry.data['host']}",
        model="Home Router",
        configuration_url=f"http://{entry.data['host']}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["device_tracker"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.session.close()

    return await hass.config_entries.async_unload_platforms(entry, ["device_tracker"])
