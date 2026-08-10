#!/usr/bin/env python3
"""Fail-closed HTTP helpers for the small, fixed skills-radar source set."""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NetworkSecurityError(RuntimeError):
    """The request violated the repository's outbound-network contract."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _normalized_hosts(hosts: Iterable[str]) -> set[str]:
    normalized = {str(host).strip().lower().rstrip(".") for host in hosts}
    if not normalized or any(not host for host in normalized):
        raise NetworkSecurityError("an explicit non-empty host allowlist is required")
    return normalized


def validate_https_url(
    url: str,
    allowed_hosts: Iterable[str],
    *,
    resolver: Callable = socket.getaddrinfo,
) -> SplitResult:
    """Validate scheme, authority, DNS result, and syntax before opening a URL."""
    if not isinstance(url, str) or not url or re.search(r"[\x00-\x20\\]", url):
        raise NetworkSecurityError("URL contains whitespace, controls, or a backslash")
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https":
        raise NetworkSecurityError("only HTTPS is allowed")
    if parsed.username is not None or parsed.password is not None:
        raise NetworkSecurityError("credentials in URLs are forbidden")
    try:
        port = parsed.port
    except ValueError as exc:
        raise NetworkSecurityError("invalid URL port") from exc
    if port not in (None, 443):
        raise NetworkSecurityError("only the default HTTPS port is allowed")
    if host not in _normalized_hosts(allowed_hosts):
        raise NetworkSecurityError(f"host is not allowlisted: {host or '<missing>'}")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise NetworkSecurityError("IP-literal destinations are forbidden")
    try:
        answers = resolver(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise NetworkSecurityError(f"DNS resolution failed for {host}: {exc}") from exc
    addresses = {str(answer[4][0]).split("%", 1)[0] for answer in answers if answer[4]}
    if not addresses:
        raise NetworkSecurityError(f"DNS returned no address for {host}")
    for address in addresses:
        try:
            resolved = ipaddress.ip_address(address)
        except ValueError as exc:
            raise NetworkSecurityError(f"DNS returned an invalid address: {address}") from exc
        if not resolved.is_global:
            raise NetworkSecurityError(f"DNS resolved to a non-public address: {address}")
    return parsed


def validate_github_api_path(path: str) -> str:
    """Accept a relative GitHub REST path, never a caller-selected host."""
    if not isinstance(path, str) or not path or re.search(r"[\x00-\x20\\]", path):
        raise NetworkSecurityError("invalid GitHub API path")
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment or path.startswith("/"):
        raise NetworkSecurityError("GitHub API path must be relative and fragment-free")
    segments = parsed.path.split("/")
    if segments[0] not in {"repos", "search"} or any(segment in {"", ".", ".."} for segment in segments):
        raise NetworkSecurityError("GitHub API path is outside the allowlisted namespaces")
    return path


def fetch_bytes(
    url: str,
    *,
    allowed_hosts: Iterable[str],
    allowed_content_types: Iterable[str],
    max_bytes: int,
    timeout: float,
    user_agent: str = "skills-radar/1.0",
    extra_headers: dict[str, str] | None = None,
    resolver: Callable = socket.getaddrinfo,
    opener=None,
) -> bytes:
    """Read one bounded response without following redirects."""
    validate_https_url(url, allowed_hosts, resolver=resolver)
    if not isinstance(max_bytes, int) or max_bytes < 1:
        raise NetworkSecurityError("max_bytes must be a positive integer")
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 60):
        raise NetworkSecurityError("timeout must be between zero and 60 seconds")
    mime_allowlist = {value.lower() for value in allowed_content_types}
    if not mime_allowlist:
        raise NetworkSecurityError("an explicit MIME allowlist is required")
    headers = {"User-Agent": user_agent, "Accept-Encoding": "identity"}
    for key, value in (extra_headers or {}).items():
        if key not in {"Accept", "Cache-Control"} or re.search(r"[\r\n]", str(value)):
            raise NetworkSecurityError(f"unsafe request header: {key}")
        headers[key] = str(value)
    request = Request(url, headers=headers)
    opener = opener or build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status != 200:
                raise NetworkSecurityError(f"unexpected HTTP status: {status}")
            content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type not in mime_allowlist:
                raise NetworkSecurityError(f"response MIME is not allowlisted: {content_type or '<missing>'}")
            length = response.headers.get("Content-Length")
            if length:
                try:
                    declared = int(length)
                except ValueError as exc:
                    raise NetworkSecurityError("invalid Content-Length") from exc
                if declared > max_bytes:
                    raise NetworkSecurityError(f"response exceeds {max_bytes} bytes")
            body = response.read(max_bytes + 1)
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            raise NetworkSecurityError(f"redirect refused: HTTP {exc.code}") from exc
        raise NetworkSecurityError(f"HTTP request failed: {exc.code}") from exc
    except URLError as exc:
        raise NetworkSecurityError(f"HTTP request failed: {exc.reason}") from exc
    if len(body) > max_bytes:
        raise NetworkSecurityError(f"response exceeds {max_bytes} bytes")
    return body
