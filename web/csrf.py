# -*- coding: utf-8 -*-
"""CSRF 防护：基于 Origin / Referer / Sec-Fetch-Site 的同源校验（OWASP 推荐的标准头校验方案）。

- 仅校验写方法（POST/PUT/PATCH/DELETE），GET/HEAD/OPTIONS 放行。
- 浏览器跨站请求必带 Origin（或 Sec-Fetch-Site=cross-site），据此拒绝。
- 允许的来源：回环地址（localhost / 127.0.0.1 / [::1]）且端口与服务端口一致，
  以及环境变量 AUTOTEST_ALLOWED_ORIGINS 中显式配置的来源。
  按回环主机名而非 Host 头比对，可同时挡住 DNS rebinding。
- 不带 Origin/Referer 的非浏览器客户端（CI webhook、curl）放行。
"""
import json
import logging
import os
from typing import Awaitable, Callable, Iterable, Optional, Tuple
from urllib.parse import urlsplit

logger = logging.getLogger("WebApp.CSRF")

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
ENV_ALLOWED_ORIGINS = "AUTOTEST_ALLOWED_ORIGINS"

ASGIApp = Callable[[dict, Callable, Callable], Awaitable[None]]


def allowed_origins_from_env() -> Tuple[str, ...]:
    raw = os.getenv(ENV_ALLOWED_ORIGINS, "")
    return tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())


def _header(scope: dict, name: bytes) -> Optional[str]:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


def _normalize_origin(url: str) -> Optional[Tuple[str, str, Optional[int]]]:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    return parts.scheme, parts.hostname.lower(), port


class CSRFOriginMiddleware:
    """纯 ASGI 中间件，不包裹响应体，对 MJPEG/SSE 流式接口无副作用。"""

    def __init__(self, app: ASGIApp, extra_allowed_origins: Iterable[str] = ()) -> None:
        self.app = app
        self.extra_allowed = frozenset(
            n for n in (_normalize_origin(o) for o in extra_allowed_origins) if n
        )

    def _is_allowed(self, url: str, server_port: Optional[int]) -> bool:
        origin = _normalize_origin(url)
        if origin is None:
            return False
        if origin in self.extra_allowed:
            return True
        _, host, port = origin
        return host in LOOPBACK_HOSTS and (server_port is None or port == server_port)

    def _reject_reason(self, scope: dict) -> Optional[str]:
        server = scope.get("server") or (None, None)
        server_port = server[1] if len(server) > 1 else None

        origin = _header(scope, b"origin")
        if origin is not None:
            return None if self._is_allowed(origin, server_port) else f"origin={origin!r}"

        referer = _header(scope, b"referer")
        if referer:
            return None if self._is_allowed(referer, server_port) else f"referer={referer!r}"

        if _header(scope, b"sec-fetch-site") == "cross-site":
            return "sec-fetch-site=cross-site"
        return None

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http" or scope.get("method") not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return

        reason = self._reject_reason(scope)
        if reason is None:
            await self.app(scope, receive, send)
            return

        logger.warning("CSRF 拦截 %s %s (%s)", scope.get("method"), scope.get("path"), reason)
        body = json.dumps(
            {"status": "error", "message": "跨站请求被拒绝 (CSRF protection)"},
            ensure_ascii=False,
        ).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})
