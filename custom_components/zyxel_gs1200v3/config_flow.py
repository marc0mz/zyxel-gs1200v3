from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import CONF_HOST, CONF_PASSWORD
import logging

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN, CONF_VERIFY_SSL, DEFAULT_SCHEME
from .api import ZyxelGS1200v3


async def _test_connection(hass: HomeAssistant, data: dict) -> None:
    api = ZyxelGS1200v3(
        data[CONF_HOST],
        data[CONF_PASSWORD],
        verify_ssl=data.get(CONF_VERIFY_SSL, False),
        scheme=data.get("scheme", DEFAULT_SCHEME),
    )
    try:
        # The supplied GS1200-8HPv3 HAR shows zindex.html as the first
        # authenticated page. system_data.js belongs to the older integration
        # and is not present on this v3 firmware.
        # async_login() returns after establishing/verifying the session;
        # _authenticated_get() returns the actual page content.
        index_html = await api._authenticated_get("zindex.html")
        if not index_html or "GS1200-8HPv3" not in index_html:
            raise CannotConnect(
                "The authenticated index did not contain the expected GS1200-8HPv3 page. "
                + api._last_http_info
            )
    except Exception as err:
        _LOGGER.exception("Zyxel GS1200v3 configuration test failed: %s", err)
        raise CannotConnect from err
    finally:
        await api.async_close()


class CannotConnect(HomeAssistantError):
    pass


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            host = user_input[CONF_HOST].strip()
            if "://" in host:
                scheme, host = host.split("://", 1)
            else:
                scheme = DEFAULT_SCHEME

            data = {
                CONF_HOST: host.rstrip("/"),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, False),
                "scheme": scheme.lower(),
            }

            await self.async_set_unique_id(f"zyxel-gs1200v3-{host.lower()}")
            self._abort_if_unique_id_configured()

            try:
                await _test_connection(self.hass, data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Zyxel GS1200v3 ({host})",
                    data=data,
                )

        schema = vol.Schema({
            vol.Required(CONF_HOST, default="192.168.68.74"): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_VERIFY_SSL, default=False): bool,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
