"""
Stealth HTTP Client
===================
Anti-detection wrapper around httpx with:
- Random User-Agent rotation
- Random request delays
- Proxy rotation
- Browser-like headers
- HTTP/2 support
"""

import asyncio
import random
from typing import List, Optional

import httpx
from fake_useragent import UserAgent

from bot.config import BotConfig, ProxySettings, StealthSettings


# ── Browser-like Headers ──────────────────────────────────────

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

AJAX_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


class StealthClient:
    """
    HTTP client with anti-detection features.
    Wraps httpx.AsyncClient with stealth capabilities.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.stealth = config.stealth
        self.proxy_cfg = config.proxy
        self._ua = UserAgent(browsers=["chrome", "firefox", "edge"])
        self._proxies = self._load_proxies()
        self._proxy_index = 0
        self._client: Optional[httpx.AsyncClient] = None

    def _load_proxies(self) -> List[str]:
        """Load proxy list from config."""
        proxies = list(self.proxy_cfg.list)

        if self.proxy_cfg.file:
            try:
                with open(self.proxy_cfg.file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            proxies.append(line)
            except FileNotFoundError:
                pass

        return proxies

    def _get_proxy(self) -> Optional[str]:
        """Get next proxy from rotation."""
        if not self.proxy_cfg.enabled or not self._proxies:
            return None

        if self.proxy_cfg.rotation:
            proxy = random.choice(self._proxies)
        else:
            proxy = self._proxies[self._proxy_index % len(self._proxies)]
            self._proxy_index += 1

        return proxy

    def _get_user_agent(self) -> str:
        """Get a random user agent string."""
        if self.stealth.random_user_agent:
            return self._ua.random
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    async def _random_delay(self):
        """Apply random delay between requests."""
        if self.stealth.random_delays:
            delay = random.uniform(
                self.stealth.delay_range.min,
                self.stealth.delay_range.max,
            )
            await asyncio.sleep(delay)

    def _build_client(self) -> httpx.AsyncClient:
        """Create a new httpx client with current settings."""
        proxy = self._get_proxy()

        transport_kwargs = {}
        if proxy:
            transport_kwargs["proxy"] = proxy

        return httpx.AsyncClient(
            http2=True,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0),
            **transport_kwargs,
        )

    def _build_headers(self, ajax: bool = False) -> dict:
        """Build request headers with random user agent."""
        headers = dict(AJAX_HEADERS if ajax else BASE_HEADERS)
        headers["User-Agent"] = self._get_user_agent()
        return headers

    async def get(self, url: str, ajax: bool = False, **kwargs) -> httpx.Response:
        """Perform a stealth GET request."""
        await self._random_delay()
        headers = self._build_headers(ajax=ajax)
        headers.update(kwargs.pop("headers", {}))

        async with self._build_client() as client:
            return await client.get(url, headers=headers, **kwargs)

    async def post(self, url: str, ajax: bool = True, **kwargs) -> httpx.Response:
        """Perform a stealth POST request."""
        await self._random_delay()
        headers = self._build_headers(ajax=ajax)
        headers.update(kwargs.pop("headers", {}))

        async with self._build_client() as client:
            return await client.post(url, headers=headers, **kwargs)

    async def session_request(
        self,
        method: str,
        url: str,
        client: httpx.AsyncClient,
        ajax: bool = False,
        **kwargs,
    ) -> httpx.Response:
        """Make a request using a persistent session (for cookie persistence)."""
        await self._random_delay()
        headers = self._build_headers(ajax=ajax)
        headers.update(kwargs.pop("headers", {}))
        return await client.request(method, url, headers=headers, **kwargs)

    def create_session(self) -> httpx.AsyncClient:
        """Create a persistent session client (caller manages lifecycle)."""
        proxy = self._get_proxy()
        transport_kwargs = {}
        if proxy:
            transport_kwargs["proxy"] = proxy

        return httpx.AsyncClient(
            http2=True,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers=self._build_headers(),
            **transport_kwargs,
        )
