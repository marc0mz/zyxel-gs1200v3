from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .api import ZyxelGS1200v3
from .coordinator import ZyxelCoordinator

PLATFORMS = [Platform.SWITCH, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = ZyxelGS1200v3(
        entry.data["host"],
        entry.data["password"],
        verify_ssl=entry.data.get("verify_ssl", False),
        scheme=entry.data.get("scheme", "http"),
    )
    coordinator = ZyxelCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.api.async_close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
