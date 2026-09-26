from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from urllib.parse import urljoin

import aiohttp
from yarl import URL
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

ALLOW_RE = re.compile(r"var\s+allow\s*=\s*(\d+)", re.I)


class ZyxelError(Exception):
    pass


class ZyxelLoginError(ZyxelError):
    pass


class ZyxelGS1200v3:
    """HTTP client for the GS1200v3 web UI.

    The v3 login page hashes the password with SHA-256 in JavaScript before
    submitting it to /logon.cgi. The switch can also terminate HTTP
    connections unexpectedly, so a successful login is verified by opening
    zindex.html instead of blindly repeating the login.
    """

    def __init__(self, host: str, password: str, verify_ssl: bool = False, scheme: str = "http"):
        self.host = host
        self.password = password
        self.scheme = scheme
        self.verify_ssl = verify_ssl
        self.base_url = f"{scheme}://{host}/"
        self._session: aiohttp.ClientSession | None = None
        # Keep parsed/scope-aware cookies, but never let aiohttp serialize them:
        # this firmware requires its session token verbatim, without quoting.
        self._cookie_jar = aiohttp.CookieJar(unsafe=True)
        self._port_url: str | None = None
        self._authenticated = False
        self._index_html: str | None = None
        self._last_http_info = "no HTTP response"

    @property
    def session(self):
        if self._session is None:
            raise RuntimeError("Session not initialized")
        return self._session

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=12, connect=5, sock_read=8)
            connector = aiohttp.TCPConnector(ssl=self.verify_ssl, limit_per_host=1)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                cookie_jar=aiohttp.DummyCookieJar(),
                headers={
                    # Match the working Chrome request captured from this exact switch.
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "it-IT,it;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "Cache-Control": "max-age=0",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-GPC": "1",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-User": "?1",
                    "Sec-Fetch-Dest": "document",
                },
            )

    async def async_close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def _allow(text: str) -> int | None:
        match = ALLOW_RE.search(text or "")
        return int(match.group(1)) if match else None

    @staticmethod
    def _login_diagnostics(text: str, location: str, status: int, cookie_names: list[str]) -> str:
        """Return non-sensitive login diagnostics suitable for an HA error."""
        lower = (text or "").lower()
        markers = []
        for marker in ("allow", "zlogin.html", "zindex.html", "password"):
            if marker in lower:
                markers.append(marker)
        return (
            f"HTTP={status} allow={ZyxelGS1200v3._allow(text)!r} "
            f"location={location!r} response_len={len(text or '')} "
            f"cookies={cookie_names!r} markers={markers!r}"
        )

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _cookie_header(self, url: str) -> str:
        """Build the switch-required raw cookie header, respecting cookie scope."""
        cookies = self._cookie_jar.filter_cookies(URL(url))
        return "; ".join(f"{m.key}={m.value}" for m in cookies.values())

    def _cookie_names(self, url: str) -> list[str]:
        """Return cookie names applicable to a URL, never their values."""
        return sorted(self._cookie_jar.filter_cookies(URL(url)).keys())

    def _request_headers(self, url: str, headers: dict | None = None) -> dict:
        result = dict(headers or {})
        result.pop("Cookie", None)
        cookie = self._cookie_header(url)
        if cookie:
            result["Cookie"] = cookie
        return result

    async def _get_text(self, path: str) -> str:
        await self._ensure_session()
        url = urljoin(self.base_url, path.lstrip("/"))
        page = path.split("?", 1)[0].rsplit("/", 1)[-1].lower()
        headers = {}
        if page == "zindex.html":
            # The browser's first authenticated navigation follows logon.cgi.
            headers["Referer"] = urljoin(self.base_url, "logon.cgi")
        elif page in {"zsystem.html", "zport.html", "mibstate.xml"}:
            # The switch serves these pages/XHRs from the zindex.html frame.
            headers["Referer"] = urljoin(self.base_url, "zindex.html")
        request_cookie_names = self._cookie_names(url)
        headers = self._request_headers(url, headers)
        async with self.session.get(url, headers=headers, allow_redirects=False) as response:
            text = await response.text(errors="ignore")
            self._cookie_jar.update_cookies(response.cookies, response_url=response.url)
            self._last_http_info = self._response_diagnostic(
                "GET", response, text, headers.get("Referer", ""), request_cookie_names
            )
            _LOGGER.debug(
                "GS1200 GET %s: status=%s content_type=%s response_len=%s "
                "has_model=%s has_login=%s cookie_names=%s referer=%s",
                page,
                response.status,
                response.headers.get("Content-Type", ""),
                len(text),
                "GS1200-8HPv3" in text,
                "zlogin.html" in text,
                self._cookie_names(url),
                headers.get("Referer", ""),
            )
            return text

    @staticmethod
    def _response_diagnostic(method, response, text, referer="", request_cookie_names=None) -> str:
        """Summarize a response without including credentials or cookie values."""
        final_path = response.url.path
        set_cookie_info = sorted(
            f"{name}(domain={morsel['domain'] or ''!r},path={morsel['path'] or ''!r},"
            f"quoted={morsel.coded_value != morsel.value},secure={bool(morsel['secure'])})"
            for name, morsel in response.cookies.items()
        )
        lower = (text or "").lower()
        allow_value = ZyxelGS1200v3._allow(text)
        err_type_match = re.search(r"var\s+errType\s*=\s*[\"']([^\"']*)", text or "", re.I)
        err_type = err_type_match.group(1) if err_type_match else None
        markers = [name for name, needle in (
            ("allow", "allow"), ("model", "gs1200-8hpv3"),
            ("login", "zlogin.html"), ("index", "zindex.html"),
        ) if needle in lower]
        return (
            f"{method} status={response.status} path={final_path!r} "
            f"content_type={response.headers.get('Content-Type', '')!r} "
            f"length={len(text or '')} allow={allow_value!r} errType={err_type!r} markers={markers!r} "
            f"request_cookie_names={request_cookie_names or []!r} "
            f"set_cookie={set_cookie_info!r} "
            f"connection={response.headers.get('Connection', '')!r} referer={referer!r}"
        )

    async def _prime_login_session(self) -> str:
        """Load zlogin.html first, like the real browser does.

        The login page establishes the same pre-login context as the browser.
        The switch sets a pre-login context here. Any cookies are retained in
        the scope-aware jar and sent verbatim by the raw-cookie request layer.
        """
        await self._ensure_session()
        url = urljoin(self.base_url, "zlogin.html")
        headers = {
            "Referer": urljoin(self.base_url, "zlogin.html"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
        }
        headers = self._request_headers(url, headers)
        async with self.session.get(url, headers=headers, allow_redirects=False) as response:
            text = await response.text(errors="ignore")
            self._cookie_jar.update_cookies(response.cookies, response_url=response.url)
            _LOGGER.debug(
                "GS1200 login page: status=%s set_cookie_header=%s",
                response.status,
                bool(response.headers.getall("Set-Cookie", [])),
            )
            return text

    async def _read_login_error(self) -> tuple[str, str]:
        """Fetch zlogin.html and extract the firmware's numeric error type."""
        try:
            html = await self._get_text("zlogin.html")
        except Exception as err:
            return "", f"fetch_error={err}"

        match = re.search(r"var\s+errType\s*=\s*[\"\']([^\"\']*)", html, re.I)
        err_type = match.group(1) if match else ""
        lower = html.lower()
        if "incorrect password" in lower:
            meaning = "incorrect_password"
        elif "other users will not be able" in lower:
            meaning = "session_already_active"
        else:
            meaning = "unknown"
        return err_type, meaning

    async def async_login(self):
        await self._ensure_session()

        # Keep the authenticated state alive; do not trigger another login on
        # every poll.
        if self._authenticated:
            return

        # Browser sequence on the v3 firmware:
        #   GET zlogin.html -> load the login page
        #   POST logon.cgi  -> submit the SHA-256 password on the same session
        # Keep the same ClientSession for the complete flow.
        await self._prime_login_session()
        _LOGGER.debug(
            "GS1200 after zlogin.html: cookie_names=%s",
            self._cookie_names(urljoin(self.base_url, "zlogin.html")),
        )

        password_hash = self._hash_password(self.password)
        post_headers = {
            "Referer": urljoin(self.base_url, "zlogin.html"),
            "Origin": self.base_url.rstrip("/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "max-age=0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "keep-alive",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
        }

        url = urljoin(self.base_url, "logon.cgi")
        _LOGGER.debug(
            "GS1200 login POST: cookie_names=%s password_length=%d",
            self._cookie_names(url),
            len(password_hash),
        )

        response_text = ""
        location = ""
        status = 0
        post_diagnostic = "no POST response"
        post_request_cookie_names = self._cookie_names(url)
        try:
            # The firmware uses a normal HTML form (application/x-www-form-urlencoded).
            # Passing a dict produces the same password=<sha256> body captured
            # in the working Chrome HAR.
            post_headers = self._request_headers(url, post_headers)
            async with self.session.post(
                url,
                data={"password": password_hash},
                headers=post_headers,
                # The browser proceeds from logon.cgi to zindex.html. Follow
                # the same redirect and validate the actual final document.
                allow_redirects=False,
            ) as response:
                status = response.status
                response_text = await response.text(errors="ignore")
                self._cookie_jar.update_cookies(response.cookies, response_url=response.url)
                location = response.headers.get("Location", "")
                post_diagnostic = self._response_diagnostic(
                    "POST", response, response_text, post_headers.get("Referer", ""),
                    post_request_cookie_names,
                )
                self._last_http_info = post_diagnostic
                _LOGGER.debug(
                    "GS1200 login response: status=%s set_cookie=%s allow=%s cookie_names=%s",
                    status,
                    bool(response.headers.getall("Set-Cookie", [])),
                    self._allow(response_text),
                    self._cookie_names(url),
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("GS1200 login POST connection failed: %s", err)

        if response_text and response.url.path.lower().endswith("/zindex.html"):
            if "GS1200-8HPv3" in response_text and "zlogin.html" not in response_text:
                self._index_html = response_text
                self._authenticated = True
                return response_text

        # The browser follows logon.cgi with zindex.html on the same
        # authenticated session. This is also the decisive authentication
        # check for the v3 firmware.
        try:
            index = await self._get_text("zindex.html")
            _LOGGER.debug(
                "GS1200 zindex verification: len=%d has_model=%s has_login_page=%s cookie_names=%s",
                len(index or ""),
                "GS1200" in (index or ""),
                "zlogin.html" in (index or ""),
                self._cookie_names(urljoin(self.base_url, "zindex.html")),
            )
            if "GS1200-8HPv3" in index and "zlogin.html" not in index:
                self._index_html = index
                self._authenticated = True
                return index
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.warning("GS1200 zindex verification failed after login: %s", err)

        allow = self._allow(response_text)
        verification_diagnostic = self._last_http_info
        diagnostics = f"POST={post_diagnostic}; verification={verification_diagnostic}"
        err_type, _ = await self._read_login_error()
        # errType is authoritative. The zlogin.html source contains BOTH
        # message strings in JavaScript, so searching the HTML text for
        # "incorrect password" is not a valid classifier.
        if err_type in {"1", "2"}:
            if err_type == "1":
                err_meaning = "incorrect_password"
            else:
                err_meaning = "session_already_active"
            diagnostics += f" login_errType={err_type!r} login_error={err_meaning}"
        else:
            err_meaning = "unknown"
            if err_type:
                diagnostics += f" login_errType={err_type!r}"
        _LOGGER.warning("GS1200 login failed: %s", diagnostics)
        if err_type == "1":
            if err_meaning == "incorrect_password":
                raise ZyxelLoginError(
                    "The switch rejected the password. " + diagnostics
                )
        if err_type == "2":
            if err_meaning == "session_already_active":
                raise ZyxelLoginError(
                    "The switch reports another web session is active. " + diagnostics
                )
        raise ZyxelLoginError(
            "Unable to establish an authenticated GS1200v3 session. "
            + diagnostics
        )

    async def _authenticated_get(self, path: str) -> str:
        await self.async_login()
        if path.lower().lstrip("/") == "zindex.html" and self._index_html is not None:
            return self._index_html
        return await self._get_text(path)

    async def _find_port_page(self) -> str:
        if self._port_url:
            return self._port_url

        index = await self._authenticated_get("zindex.html")
        soup = BeautifulSoup(index, "html.parser")
        candidates = []
        for tag in soup.find_all(["a", "frame", "iframe"]):
            href = tag.get("href") or tag.get("src")
            if href:
                low = href.lower()
                if "port" in low:
                    candidates.append(urljoin(self.base_url, href))

        # Common v3 name first, then any discovered port page.
        for candidate in candidates:
            if "port" in candidate.lower():
                self._port_url = candidate
                break

        if not self._port_url:
            # The v3 UI commonly exposes the Port page as a direct HTML page.
            self._port_url = urljoin(self.base_url, "zPort.html")

        return self._port_url

    @staticmethod
    def _num(text: str):
        text = (text or "").strip().replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    def _parse_ports(self, html: str) -> dict[int, dict]:
        soup = BeautifulSoup(html, "html.parser")
        result = {}

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue
                values = [c.get_text(" ", strip=True) for c in cells]
                port = None
                for value in values[:3]:
                    match = re.fullmatch(r"(?:Port\s*)?(\d{1,2})", value, re.I)
                    if match:
                        port = int(match.group(1))
                        break
                if port not in range(1, 9):
                    continue

                text = " | ".join(values)
                low = text.lower()
                poe_enabled = "enable" in low and "disable" not in low

                # Prefer a numeric value near labels such as PoE(W), Power,
                # Consuming Power. This also tolerates the v3 table changing.
                power = None
                for value in values:
                    if re.search(r"poe|power|watt|consum", value, re.I):
                        m = re.search(r"(-?\d+(?:[.,]\d+)?)", value)
                        if m:
                            power = self._num(m.group(1))
                            break

                result[port] = {
                    "poe_enabled": poe_enabled,
                    "power_w": power if power is not None else 0.0,
                    "raw": values,
                }

        # The v3 Port page has 4 PoE-capable ports on the 8HP model.
        return {p: result.get(p, {
            "poe_enabled": False,
            "power_w": 0.0,
            "raw": [],
        }) for p in range(1, 5)}

    @staticmethod
    def _decode_poe_power(raw_value: int) -> float:
        return round((raw_value >> 4) + (raw_value & 0xF) / 10.0, 1)

    def _parse_system_poe(self, html: str) -> dict[int, dict]:
        """Parse the actual PoE variables embedded in zSystem.html."""
        cfg_match = re.search(r"var\s+poe_cfg\s*=\s*\{.*?max_poe_port\s*:\s*(\d+).*?\}", html, re.S)
        state_match = re.search(r'var\s+poe_state\s*=\s*"([^"]+)"', html)
        if not state_match:
            raise ZyxelError("zSystem.html did not contain poe_state")

        state_parts = state_match.group(1).split(";")
        if len(state_parts) < 2:
            raise ZyxelError("Invalid poe_state format")

        try:
            controls = [int(x) for x in state_parts[1].split(",") if x != ""]
        except ValueError as err:
            raise ZyxelError("Invalid PoE control data") from err

        result = {}
        for idx in range(4):
            port = idx + 1
            row = state_parts[idx + 2].split(",") if idx + 2 < len(state_parts) else []
            enabled = bool(controls[idx]) if idx < len(controls) else False
            power = 0.0
            if len(row) >= 3:
                try:
                    power = self._decode_poe_power(int(row[2]))
                except ValueError:
                    power = 0.0
            result[port] = {
                "poe_enabled": enabled,
                "power_w": power,
                "poe_status": int(row[0]) if row and row[0].isdigit() else 0,
                "poe_class": int(row[1]) if len(row) > 1 and row[1].isdigit() else 0,
            }
        return result

    async def async_get_state(self) -> dict:
        html = await self._authenticated_get("zSystem.html")
        ports = self._parse_system_poe(html)
        config = await self._get_port_config()
        for port in range(1, config["max_port"] + 1):
            port_data = ports.setdefault(port, {})
            port_data["ethernet_enabled"] = bool(
                config["port_state"] & (1 << (port - 1))
            )
        return {"ports": ports}

    async def _get_port_config(self) -> dict:
        """Read the live form state embedded in the firmware's zPort.html."""
        text = await self._authenticated_get("zPort.html")

        max_port = self._extract_int(text, r'var\s+max_port_num\s*=\s*(\d+)')
        port_poe = self._extract_int(text, r'var\s+portPoE\s*=\s*[\'\"]?(\d+)')
        info_match = re.search(r'var\s+all_info\s*=\s*\{(.*?)\}', text, re.S)
        if max_port is None or port_poe is None or not info_match:
            raise ZyxelError("zPort.html did not contain the expected live port configuration")

        def read_array(name: str) -> list[int] | None:
            match = re.search(rf'\b{name}\s*:\s*\[([^\]]*)\]', info_match.group(1), re.I)
            if not match:
                return None
            try:
                return [int(value.strip()) for value in match.group(1).split(",") if value.strip()]
            except ValueError:
                return None

        states = read_array("state")
        flow_control = read_array("fc_cfg")
        speed_config = read_array("spd_cfg")
        ability = read_array("ability")
        if any(values is None or len(values) < max_port for values in (states, flow_control, speed_config, ability)):
            raise ZyxelError("zPort.html contained incomplete all_info port arrays")

        # Match loada() in the switch's zPort.html. It populates the hidden
        # g_port_speedN fields from spd_cfg/ability before port_set() submits.
        ability_to_speed = {16: 1, 4: 2, 8: 3, 1: 4, 2: 5}
        speeds = []
        for index in range(max_port):
            if speed_config[index] == 0 and ability[index] in (31, 16):
                speeds.append(0 if ability[index] == 31 else 1)
            else:
                speeds.append(ability_to_speed.get(ability[index], 0))

        # port_set() reconstructs these masks from the select controls, whose
        # selected indexes loada() initializes from all_info.state/fc_cfg.
        port_state = sum((value & 1) << index for index, value in enumerate(states[:max_port]))
        port_flctl = sum((value & 1) << index for index, value in enumerate(flow_control[:max_port]))

        return {
            "max_port": max_port,
            "port_state": port_state,
            "port_flctl": port_flctl,
            "port_poe": port_poe,
            "speeds": speeds[:max_port],
        }

    @staticmethod
    def _extract_int(text: str, pattern: str) -> int | None:
        match = re.search(pattern, text or "", re.I)
        return int(match.group(1)) if match else None

    async def async_set_poe(self, port: int, enabled: bool):
        """Change one PoE port using the firmware's zPort_setting.cgi form."""
        if port not in range(1, 5):
            raise ZyxelError("GS1200-8HPv3 PoE ports are 1-4")

        cfg = await self._get_port_config()
        if cfg["max_port"] < 4:
            raise ZyxelError(
                f"Switch reports only {cfg['max_port']} physical ports; expected GS1200-8HPv3 layout"
            )

        bit = 1 << (port - 1)
        poe_bitmap = cfg["port_poe"]
        if enabled:
            poe_bitmap |= bit
        else:
            poe_bitmap &= ~bit

        # This is the exact payload shape generated by zPort.html in the
        # supplied GS1200v3 firmware. For a PoE-only change the firmware UI
        # keeps g_port_map at zero and marks the changed PoE port in
        # g_port_map_poe. g_port_poe is the complete 4-port bitmap.
        data = {
            "g_port_state": str(cfg["port_state"]),
            "g_port_flwcl": str(cfg["port_flctl"]),
            "g_port_map": "0",
            "g_port_map_poe": str(bit),
            "g_port_poe": str(poe_bitmap),
        }
        for index, speed in enumerate(cfg["speeds"]):
            data[f"g_port_speed{index}"] = str(speed)

        url = urljoin(self.base_url, "zport_setting.cgi")
        headers = {
            "Referer": urljoin(self.base_url, "zPort.html"),
            "Origin": self.base_url.rstrip("/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.5",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        _LOGGER.debug(
            "GS1200 PoE write port=%s enabled=%s map_poe=%s poe_bitmap=%s",
            port,
            enabled,
            bit,
            poe_bitmap,
        )

        try:
            headers = self._request_headers(url, headers)
            async with self.session.post(
                url,
                data=data,
                headers=headers,
                allow_redirects=False,
            ) as response:
                text = await response.text(errors="ignore")
                self._cookie_jar.update_cookies(response.cookies, response_url=response.url)
                if response.status >= 400:
                    raise ZyxelError(
                        f"zport_setting.cgi returned HTTP {response.status}"
                    )
                if "zlogin.html" in text and "GS1200" not in text:
                    raise ZyxelLoginError("Switch session expired while changing PoE state")
        except ZyxelError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZyxelError(f"PoE write request failed: {err}") from err

        # Read back the complete state instead of assuming the switch accepted
        # the requested bit. This prevents Home Assistant from showing a stale
        # state if the firmware rejected the change.
        state = await self.async_get_state()
        actual = state["ports"].get(port, {}).get("poe_enabled")
        if bool(actual) != bool(enabled):
            raise ZyxelError(
                f"Switch did not apply PoE state on port {port} (requested={enabled}, actual={actual})"
            )

    async def async_set_port_enabled(self, port: int, enabled: bool):
        """Enable or disable the Ethernet link on one physical port."""
        cfg = await self._get_port_config()
        if port not in range(1, cfg["max_port"] + 1):
            raise ZyxelError(
                f"Port must be between 1 and {cfg['max_port']} for this switch"
            )

        bit = 1 << (port - 1)
        port_state = cfg["port_state"] | bit if enabled else cfg["port_state"] & ~bit
        data = {
            "g_port_state": str(port_state),
            "g_port_flwcl": str(cfg["port_flctl"]),
            "g_port_map": str(bit),
            "g_port_map_poe": "0",
            "g_port_poe": str(cfg["port_poe"]),
        }
        for index, speed in enumerate(cfg["speeds"]):
            data[f"g_port_speed{index}"] = str(speed)

        url = urljoin(self.base_url, "zport_setting.cgi")
        headers = {
            "Referer": urljoin(self.base_url, "zPort.html"),
            "Origin": self.base_url.rstrip("/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.5",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            headers = self._request_headers(url, headers)
            async with self.session.post(
                url, data=data, headers=headers, allow_redirects=False
            ) as response:
                text = await response.text(errors="ignore")
                self._cookie_jar.update_cookies(response.cookies, response_url=response.url)
                if response.status >= 400:
                    raise ZyxelError(
                        f"zport_setting.cgi returned HTTP {response.status}"
                    )
                if "zlogin.html" in text and "GS1200" not in text:
                    raise ZyxelLoginError(
                        "Switch session expired while changing Ethernet port state"
                    )
        except ZyxelError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZyxelError(f"Ethernet port write request failed: {err}") from err

        state = await self.async_get_state()
        actual = state["ports"].get(port, {}).get("ethernet_enabled")
        if bool(actual) != bool(enabled):
            raise ZyxelError(
                f"Switch did not apply Ethernet state on port {port} "
                f"(requested={enabled}, actual={actual})"
            )
