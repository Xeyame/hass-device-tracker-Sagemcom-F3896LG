import logging
from typing import Any, Dict

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.components.device_tracker.config_entry import SourceType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback

from .coordinator import RouterCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN = "router_tracker"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up router_tracker device_tracker with dynamic discovery."""
    coordinator: RouterCoordinator = hass.data[DOMAIN][entry.entry_id]

    tracked_macs: set[str] = set()
    platform_entities: dict[str, RouterDeviceTracker] = {}

    #
    # Helper to add any NEW devices discovered from coordinator.data
    #
    @callback
    def _async_process_new_devices():
        hosts = coordinator.data.get("hosts", [])

        new_entities = []

        for dev in hosts:
            mac = dev.get("mac")
            if not mac:
                continue

            mac = mac.lower()

            # Skip router itself if needed
            if dev.get("is_router"):
                continue

            # Already added?
            if mac in tracked_macs:
                continue

            entity = RouterDeviceTracker(coordinator, entry.entry_id, dev)
            tracked_macs.add(mac)
            platform_entities[mac] = entity
            new_entities.append(entity)

            _LOGGER.debug("Discovered NEW device: %s", mac)

        if new_entities:
            async_add_entities(new_entities, update_before_add=True)

    #
    # Run discovery immediately with startup data
    #
    _async_process_new_devices()

    #
    # Register listener for every coordinator refresh
    #
    coordinator.async_add_listener(_async_process_new_devices)
    return True


class RouterDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Representation of a connected client device."""

    _attr_entity_registry_enabled_default = True  # auto-enable

    def __init__(self, coordinator: RouterCoordinator, entry_id: str, device: Dict[str, Any]):
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.device = device

        mac = device["mac"].lower()

        hostname = device.get("hostname")
        if not hostname or hostname.lower() == "unknown":
            hostname = mac  # fallback to MAC

        self._attr_unique_id = mac
        self._attr_mac_address = mac
        self._attr_name = hostname
        self._attr_source_type = SourceType.ROUTER

        self._attr_ip_address = device.get("ip")
        self._attr_is_connected = device.get("connected", False)

        _LOGGER.debug("Created tracker entity for %s (%s)", hostname, mac)

    @property
    def device_info(self):
        """Expose each device as a full device in Home Assistant."""
        mac = self.device["mac"].lower()

        return {
            "identifiers": {(DOMAIN, mac)},
            "name": self._attr_name,
            "manufacturer": "Router Client",
            "model": "Network Device",
            "connections": {("mac", mac)},
            "via_device": (DOMAIN, f"router-{self.entry_id}"),
        }

    @property
    def is_connected(self) -> bool:
        mac = self._attr_unique_id
        for h in self.coordinator.data.get("hosts", []):
            if h.get("mac", "").lower() == mac:
                return h.get("connected", False)
        return False

    @property
    def extra_state_attributes(self):
        mac = self._attr_unique_id
        for host in self.coordinator.data.get("hosts", []):
            if host.get("mac", "").lower() == mac:
                return {
                    "hostname": host.get("hostname"),
                    "ip": host.get("ip"),
                    "interface": host.get("interface"),
                    "device_type": host.get("device_type"),
                    "rssi": host.get("wifi", {}).get("rssi"),
                    "raw": host.get("raw"),
                }
        return {}

    async def async_update(self):
        """Trigger manual update if needed."""
        self._attr_is_connected = self.is_connected
