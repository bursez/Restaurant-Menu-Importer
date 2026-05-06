from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


class UrlValidationError(ValueError):
    pass


_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def _is_blocked_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _validate_hostname(hostname: str) -> str:
    normalized_hostname = hostname.rstrip(".").lower()
    if not normalized_hostname:
        raise UrlValidationError("URL must include a host")
    if normalized_hostname in _BLOCKED_HOSTNAMES or normalized_hostname.endswith(".localhost"):
        raise UrlValidationError("Private or internal URLs are not allowed")

    try:
        address = ipaddress.ip_address(normalized_hostname.strip("[]"))
    except ValueError:
        return normalized_hostname

    if _is_blocked_ip(address):
        raise UrlValidationError("Private or internal URLs are not allowed")
    return normalized_hostname


def validate_url_format(url: str) -> str:
    normalized_url = url.strip()
    if not normalized_url:
        raise UrlValidationError("URL cannot be empty")

    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"}:
        raise UrlValidationError("Only HTTP and HTTPS URLs are supported")
    if parsed.username or parsed.password:
        raise UrlValidationError("URL credentials are not allowed")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise UrlValidationError("URL port is invalid")
    if parsed.hostname is None:
        raise UrlValidationError("URL must include a host")

    _validate_hostname(parsed.hostname)
    return normalized_url


async def validate_public_url(url: str) -> str:
    normalized_url = validate_url_format(url)
    parsed = urlparse(normalized_url)
    assert parsed.hostname is not None
    hostname = _validate_hostname(parsed.hostname)

    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, hostname, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlValidationError("URL host could not be resolved") from exc

    if not addresses:
        raise UrlValidationError("URL host could not be resolved")

    for address_info in addresses:
        socket_address = address_info[4][0]
        try:
            ip_address = ipaddress.ip_address(socket_address)
        except ValueError as exc:
            raise UrlValidationError("URL host resolved to an invalid address") from exc
        if _is_blocked_ip(ip_address):
            raise UrlValidationError("Private or internal URLs are not allowed")

    return normalized_url
