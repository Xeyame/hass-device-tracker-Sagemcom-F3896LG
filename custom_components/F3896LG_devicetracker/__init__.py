import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import device_registry as dr

from .coordinator import RouterCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN = "F3896LG_devicetracker"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the F3896LG_devicetracker component."""
    _LOGGER.debug("F3896LG_devicetracker async_setup called")
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up F3896LG_devicetracker from a config entry."""
    _LOGGER.debug("Setting up entry %s for F3896LG_devicetracker", entry.title)

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
        manufacturer="Sagemcom",
        name=f"Sagemcom F3896LG",
        model="F3896LG",
        configuration_url=f"http://{entry.data['host']}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["device_tracker"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.session.close()

    return await hass.config_entries.async_unload_platforms(entry, ["device_tracker"])
