import asyncio
import importlib.util
import sys
from pathlib import Path
from yarl import URL

api_path = Path(__file__).resolve().parents[1] / "custom_components" / "zyxel_gs1200v3" / "api.py"
spec = importlib.util.spec_from_file_location("zyxel_api", api_path)
api_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api_module
spec.loader.exec_module(api_module)

class Response:
    status = 200
    url = URL("http://switch/zport_setting.cgi")
    cookies = {}
    async def text(self, errors="ignore"):
        return "ok"
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False

class Session:
    closed = False
    def __init__(self):
        self.payloads = []
    def post(self, url, data, headers, allow_redirects):
        self.payloads.append((url, dict(data), allow_redirects))
        return Response()

async def main():
    client = api_module.ZyxelGS1200v3("test-switch", "unused")
    session = Session()
    client._session = session
    config = {"max_port": 8, "port_state": 255, "port_flctl": 0,
              "port_poe": 15, "speeds": [0] * 8}
    async def get_config():
        return config
    async def get_state():
        return {"ports": {4: {"ethernet_enabled": False}}}
    client._get_port_config = get_config
    client.async_get_state = get_state
    await client.async_set_port_enabled(4, False)
    url, data, redirects = session.payloads[-1]
    assert data["g_port_state"] == "247"
    assert data["g_port_map"] == "8"
    assert data["g_port_map_poe"] == "0"
    assert data["g_port_poe"] == "15"
    assert data["g_port_flwcl"] == "0"
    assert redirects is False
    async def get_state_on():
        return {"ports": {4: {"ethernet_enabled": True}}}
    client.async_get_state = get_state_on
    await client.async_set_port_enabled(4, True)
    _, data, _ = session.payloads[-1]
    assert data["g_port_state"] == "255"
    assert data["g_port_map"] == "8"
    assert data["g_port_poe"] == "15"
    print("PASS: Ethernet disable/enable payloads preserve other port, PoE, speed and flow settings")

asyncio.run(main())

