"""Endpoint validation for model calls.

The policy deliberately runs immediately before every network operation.  It
does not follow redirects, and blocks private/special-use DNS answers unless
the hostname or address is explicitly allowlisted.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

from app.config import settings
from app.llm.errors import LLMAdapterError, LLMErrorCategory

Resolver = Callable[[str, int | None], Iterable[str]]


def _system_resolver(hostname: str, port: int | None) -> set[str]:
    return {
        item[4][0]
        for item in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    }


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


class EndpointPolicy:
    def __init__(
        self,
        *,
        app_env: str | None = None,
        allowlist: Iterable[str] | None = None,
        resolver: Resolver | None = None,
    ) -> None:
        self.app_env = (app_env or settings.app_env).casefold()
        self.allowlist = frozenset(
            item.strip().casefold()
            for item in (allowlist or settings.model_endpoint_allowlist_values)
            if item.strip()
        )
        self._resolver = resolver or _system_resolver

    async def validate(self, url: str) -> None:
        parts = urlsplit(url)
        hostname = (parts.hostname or "").casefold()
        if parts.scheme not in {"http", "https"} or not hostname:
            raise self._blocked()
        if parts.username is not None or parts.password is not None:
            raise self._blocked()
        if parts.fragment:
            raise self._blocked()
        if self.app_env != "local" and parts.scheme != "https":
            raise self._blocked()
        hostname_allowed = hostname in self.allowlist
        try:
            literal = ipaddress.ip_address(hostname)
            addresses = {str(literal)}
        except ValueError:
            try:
                addresses = set(
                    await asyncio.to_thread(self._resolver, hostname, parts.port)
                )
            except (OSError, ValueError):
                raise LLMAdapterError(
                    LLMErrorCategory.UNAVAILABLE,
                    "The model endpoint could not be resolved.",
                    retryable=True,
                ) from None
        if not addresses:
            raise self._blocked()
        if hostname_allowed:
            return
        if any(
            address.casefold() not in self.allowlist and not _is_public(address)
            for address in addresses
        ):
            raise self._blocked()

    @staticmethod
    def _blocked() -> LLMAdapterError:
        return LLMAdapterError(
            LLMErrorCategory.ENDPOINT_BLOCKED,
            "The model endpoint is not allowed by server policy.",
            retryable=False,
        )


def test_endpoint_policy(*, allowlist: Iterable[str] = ()) -> EndpointPolicy:
    """Build a deterministic public-DNS policy for injected HTTP transports."""

    return EndpointPolicy(
        app_env="local",
        allowlist=allowlist,
        resolver=lambda hostname, port: {"93.184.216.34"},
    )
