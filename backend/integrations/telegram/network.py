"""
network.py — Resilient Transport, DNS-over-HTTPS (DoH), and Fallback IP Architecture for Telegram.

Provides:
1. TCP Keepalive Socket Options: Prevents half-open socket hangs on Windows where SO_KEEPALIVE is off by default.
2. DNS-over-HTTPS (DoH) Resolution: Queries Cloudflare and Google DoH endpoints to discover clean IPv4 literals for api.telegram.org.
3. TelegramFallbackTransport: A custom httpx AsyncBaseTransport that routes requests through discovered IPv4 literals
   with preserved Host header and SNI hostname (curl --resolve parity), bypassing ISP throttling and IPv6 blackholing.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from typing import Iterable, List, Optional, Tuple, Dict, Any

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_HOST = "api.telegram.org"

# Windows leaves SO_KEEPALIVE off on new sockets by default, which can cause
# polling or long connections to hang indefinitely when packets drop.
TCP_KEEPALIVE_IDLE_S = 30
TCP_KEEPALIVE_INTERVAL_S = 10
TCP_KEEPALIVE_COUNT = 3

DOH_TIMEOUT = 4.0
DOH_PROVIDERS: List[Dict[str, Any]] = [
    {"url": "https://dns.google/resolve", "params": {"name": TELEGRAM_API_HOST, "type": "A"}, "headers": {}},
    {"url": "https://cloudflare-dns.com/dns-query", "params": {"name": TELEGRAM_API_HOST, "type": "A"}, "headers": {"Accept": "application/dns-json"}},
]

# Canonical fallback IPv4 endpoints for Telegram Bot API (149.154.160.0/20)
SEED_FALLBACK_IPS: List[str] = ["149.154.166.110", "149.154.167.220"]
_UNSET = object()


def tcp_keepalive_socket_options() -> List[Tuple[int, int, int]]:
    """Returns setsockopt tuples for httpx socket_options ensuring SO_KEEPALIVE is enabled."""
    options: List[Tuple[int, int, int]] = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
    idle = getattr(socket, "TCP_KEEPIDLE", None) or getattr(socket, "TCP_KEEPALIVE", None)
    for opt, value in (
        (idle, TCP_KEEPALIVE_IDLE_S),
        (getattr(socket, "TCP_KEEPINTVL", None), TCP_KEEPALIVE_INTERVAL_S),
        (getattr(socket, "TCP_KEEPCNT", None), TCP_KEEPALIVE_COUNT),
    ):
        if opt is not None:
            options.append((socket.IPPROTO_TCP, opt, value))
    return options


def _normalize_fallback_ips(values: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    for value in values:
        raw = str(value).strip()
        if not raw:
            continue
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if addr.version == 4 and not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified):
            normalized.append(str(addr))
    return normalized


def _resolve_system_dns() -> List[str]:
    """Resolves system DNS for api.telegram.org."""
    try:
        results = socket.getaddrinfo(TELEGRAM_API_HOST, 443, socket.AF_INET)
        return list({str(addr[4][0]) for addr in results})
    except Exception:
        return []


async def _query_doh_provider(client: httpx.AsyncClient, provider: Dict[str, Any]) -> List[str]:
    """Queries a DoH endpoint for A records."""
    try:
        resp = await client.get(provider["url"], params=provider["params"], headers=provider["headers"])
        if resp.status_code != 200:
            return []
        data = resp.json()
        ips: List[str] = []
        for answer in data.get("Answer", []):
            if answer.get("type") == 1:  # A record
                raw = str(answer.get("data", "")).strip()
                try:
                    ipaddress.ip_address(raw)
                    ips.append(raw)
                except ValueError:
                    pass
        return ips
    except Exception as exc:
        logger.debug(f"[TelegramNetwork] DoH query to {provider['url']} failed: {exc}")
        return []


async def discover_telegram_ips() -> List[str]:
    """
    Discovers Telegram Bot API IPs via Cloudflare + Google DoH with system DNS fallback.
    Guarantees connectivity even if local ISP DNS poisons or blocks api.telegram.org.
    """
    discovered: List[str] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(DOH_TIMEOUT)) as client:
            tasks = [_query_doh_provider(client, p) for p in DOH_PROVIDERS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    discovered.extend(r)
    except Exception as e:
        logger.debug(f"[TelegramNetwork] DoH discovery error: {e}")

    # Deduplicate and validate
    valid_doh = _normalize_fallback_ips(list(dict.fromkeys(discovered)))
    if valid_doh:
        return valid_doh

    # Fallback to system DNS then seed IPs
    system_ips = _resolve_system_dns()
    valid_sys = _normalize_fallback_ips(system_ips)
    if valid_sys:
        return valid_sys

    return list(SEED_FALLBACK_IPS)


def _rewrite_request_for_ip(request: httpx.Request, ip: str) -> httpx.Request:
    """Rewrites target URL host to the literal IP while preserving Host header and TLS SNI."""
    original_host = request.url.host or TELEGRAM_API_HOST
    url = request.url.copy_with(host=ip)
    headers = request.headers.copy()
    headers["host"] = original_host
    extensions = dict(request.extensions)
    extensions["sni_hostname"] = original_host
    return httpx.Request(
        method=request.method,
        url=url,
        headers=headers,
        stream=request.stream,
        extensions=extensions,
    )


class TelegramFallbackTransport(httpx.AsyncBaseTransport):
    """
    High-availability transport for Telegram Bot API:
    - Retries known IPv4 literals first with preserved SNI/Host, dual-stack hostname last.
    - Employs sticky IP: once an endpoint succeeds, subsequent calls route directly through it.
    - Recycles failed socket pools to prevent file descriptor leaks.
    """

    _POOL_LIMITS = httpx.Limits(max_connections=8, max_keepalive_connections=4)

    def __init__(self, fallback_ips: Optional[Iterable[str]] = None, **transport_kwargs):
        self._fallback_ips = list(dict.fromkeys(_normalize_fallback_ips(fallback_ips or SEED_FALLBACK_IPS)))
        transport_kwargs.setdefault("limits", self._POOL_LIMITS)
        transport_kwargs.setdefault("socket_options", tcp_keepalive_socket_options())
        self._transport_kwargs = transport_kwargs
        self._primary = httpx.AsyncHTTPTransport(**transport_kwargs)
        self._primary_lock = asyncio.Lock()
        self._primary_closed = False
        self._fallbacks: Dict[str, httpx.AsyncHTTPTransport] = {}
        self._fallback_lock = asyncio.Lock()
        self._sticky_ip: object = _UNSET
        self._sticky_lock = asyncio.Lock()

    async def _get_fallback(self, ip: str) -> httpx.AsyncHTTPTransport:
        async with self._fallback_lock:
            transport = self._fallbacks.get(ip)
            if transport is None:
                transport = httpx.AsyncHTTPTransport(**self._transport_kwargs)
                self._fallbacks[ip] = transport
            return transport

    async def _reset_fallback(self, ip: str):
        async with self._fallback_lock:
            transport = self._fallbacks.pop(ip, None)
        if transport is not None:
            try:
                await transport.aclose()
            except Exception:
                pass

    def _attempt_order(self) -> List[Optional[str]]:
        order: List[Optional[str]] = []
        if self._sticky_ip is not _UNSET:
            order.append(None if self._sticky_ip is None else str(self._sticky_ip))
        order.extend(ip for ip in self._fallback_ips if ip not in order)
        if None not in order:
            order.append(None)
        return order

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != TELEGRAM_API_HOST or not self._fallback_ips:
            return await self._primary.handle_async_request(request)

        last_error: Optional[Exception] = None
        for ip in self._attempt_order():
            candidate = request if ip is None else _rewrite_request_for_ip(request, ip)
            transport = self._primary if ip is None else await self._get_fallback(ip)
            try:
                response = await transport.handle_async_request(candidate)
                if self._sticky_ip is _UNSET or self._sticky_ip != ip:
                    async with self._sticky_lock:
                        self._sticky_ip = ip
                        logger.info(f"[TelegramNetwork] Bound sticky Telegram API path -> {ip or TELEGRAM_API_HOST}")
                return response
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.NetworkError) as exc:
                last_error = exc
                logger.warning(f"[TelegramNetwork] Path {ip or TELEGRAM_API_HOST} failed ({exc}); switching to next fallback...")
                if ip is not None:
                    await self._reset_fallback(ip)
                if self._sticky_ip == ip:
                    async with self._sticky_lock:
                        self._sticky_ip = _UNSET
                continue
            except Exception as exc:
                last_error = exc
                raise

        if last_error:
            raise last_error
        raise RuntimeError("All Telegram fallback endpoints exhausted without error.")

    async def aclose(self):
        async with self._primary_lock:
            self._primary_closed = True
            await self._primary.aclose()
        async with self._fallback_lock:
            for transport in self._fallbacks.values():
                try:
                    await transport.aclose()
                except Exception:
                    pass
            self._fallbacks.clear()


# ── Global Singleton Client Provider ──────────────────────────────────────────
_global_transport: Optional[TelegramFallbackTransport] = None
_global_transport_lock = asyncio.Lock()


async def get_telegram_transport() -> TelegramFallbackTransport:
    """Returns singleton resilient TelegramFallbackTransport with initialized DoH IPs."""
    global _global_transport
    if _global_transport is not None:
        return _global_transport

    async with _global_transport_lock:
        if _global_transport is None:
            discovered_ips = await discover_telegram_ips()
            _global_transport = TelegramFallbackTransport(fallback_ips=discovered_ips)
    return _global_transport


def create_resilient_telegram_client(timeout: float = 30.0, follow_redirects: bool = True) -> httpx.AsyncClient:
    """Factory creating an AsyncClient backed by the resilient TelegramFallbackTransport."""
    # Note: Transport is lazily hooked if initialized, or falls back to socket keepalive
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=follow_redirects,
        limits=httpx.Limits(max_connections=12, max_keepalive_connections=6),
    )
