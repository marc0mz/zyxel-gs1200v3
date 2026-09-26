from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTR_PORT
from .coordinator import ZyxelCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZyxelCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        ZyxelPoESwitch(coordinator, port)
        for port in coordinator.data["ports"]
        if port <= 4
    ]
    entities.extend(
        ZyxelEthernetSwitch(coordinator, port)
        for port in coordinator.data["ports"]
    )
    async_add_entities(entities)


class ZyxelPoESwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, port: int):
        super().__init__(coordinator)
        self._port = port
        self._attr_unique_id = f"{coordinator.api.host}-poe-{port}"
        self._attr_name = f"Port {port} PoE"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.api.host)},
            "name": f"Zyxel GS1200-8HPv3 ({self.coordinator.api.host})",
            "manufacturer": "Zyxel",
            "model": "GS1200-8HPv3",
        }

    @property
    def is_on(self):
        return self.coordinator.data["ports"][self._port]["poe_enabled"]

    @property
    def extra_state_attributes(self):
        data = dict(self.coordinator.data["ports"][self._port])
        data[ATTR_PORT] = self._port
        return data

    async def async_turn_on(self):
        await self.coordinator.api.async_set_poe(self._port, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        await self.coordinator.api.async_set_poe(self._port, False)
        await self.coordinator.async_request_refresh()


class ZyxelEthernetSwitch(CoordinatorEntity, SwitchEntity):
    """Administrative enable/disable control for one Ethernet port."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:ethernet"

    def __init__(self, coordinator, port: int):
        super().__init__(coordinator)
        self._port = port
        self._attr_unique_id = f"{coordinator.api.host}-ethernet-{port}"
        self._attr_name = f"Port {port} Ethernet"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.api.host)},
            "name": f"Zyxel GS1200-8HPv3 ({self.coordinator.api.host})",
            "manufacturer": "Zyxel",
            "model": "GS1200-8HPv3",
        }

    @property
    def is_on(self):
        return self.coordinator.data["ports"][self._port]["ethernet_enabled"]

    @property
    def extra_state_attributes(self):
        return {ATTR_PORT: self._port}

    async def async_turn_on(self):
        await self.coordinator.api.async_set_port_enabled(self._port, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        await self.coordinator.api.async_set_port_enabled(self._port, False)
        await self.coordinator.async_request_refresh()
