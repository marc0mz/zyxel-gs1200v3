from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZyxelCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZyxelCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ZyxelPowerSensor(coordinator, port)
        for port in coordinator.data["ports"]
        if port <= 4
    ])


class ZyxelPowerSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = "power"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, port: int):
        super().__init__(coordinator)
        self._port = port
        self._attr_unique_id = f"{coordinator.api.host}-power-{port}"
        self._attr_name = f"Port {port} PoE power"

    @property
    def native_value(self):
        return self.coordinator.data["ports"][self._port]["power_w"]

    @property
    def extra_state_attributes(self):
        return dict(self.coordinator.data["ports"][self._port])

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.api.host)},
            "name": f"Zyxel GS1200-8HPv3 ({self.coordinator.api.host})",
            "manufacturer": "Zyxel",
            "model": "GS1200-8HPv3",
        }
