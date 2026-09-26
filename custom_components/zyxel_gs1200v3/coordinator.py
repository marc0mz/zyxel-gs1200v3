from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZyxelGS1200v3
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class ZyxelCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, api: ZyxelGS1200v3):
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name="Zyxel GS1200v3",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self):
        try:
            return await self.api.async_get_state()
        except Exception as err:
            raise UpdateFailed(str(err)) from err
