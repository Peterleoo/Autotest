# -*- coding: utf-8 -*-
"""CSRF 防护：跨站浏览器请求不得调用写接口；同源页面与非浏览器客户端（CI/curl）不受影响"""
import asyncio

import pytest

from web.csrf import CSRFOriginMiddleware

SERVER = ("127.0.0.1", 8000)


async def _ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _call(method="POST", headers=None, extra_origins=(), scope_type="http"):
    mw = CSRFOriginMiddleware(_ok_app, extra_allowed_origins=extra_origins)
    scope = {
        "type": scope_type,
        "method": method,
        "path": "/api/sessions/create",
        "server": SERVER,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    asyncio.run(mw(scope, receive, send))
    return sent[0]["status"]


@pytest.mark.parametrize("origin", [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://[::1]:8000",
])
def test_same_origin_post_allowed(origin):
    assert _call(headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"}) == 200


@pytest.mark.parametrize("origin", [
    "https://evil.example.com",
    "http://evil.example.com:8000",   # DNS rebinding 场景
    "http://localhost:3000",          # 本机其他端口的页面
    "null",                           # 沙箱 iframe / file://
])
def test_cross_origin_post_rejected(origin):
    assert _call(headers={"Origin": origin}) == 403


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_other_unsafe_methods_rejected_cross_origin(method):
    assert _call(method=method, headers={"Origin": "https://evil.example.com"}) == 403


def test_cross_site_fetch_metadata_rejected_even_without_origin():
    assert _call(headers={"Sec-Fetch-Site": "cross-site"}) == 403


def test_referer_used_when_origin_missing():
    assert _call(headers={"Referer": "https://evil.example.com/page"}) == 403
    assert _call(headers={"Referer": "http://127.0.0.1:8000/"}) == 200


def test_non_browser_client_without_headers_allowed():
    """CI webhook / curl 不带 Origin/Referer，应放行"""
    assert _call() == 200


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_safe_methods_not_checked(method):
    assert _call(method=method, headers={"Origin": "https://evil.example.com"}) == 200


def test_extra_allowed_origin_from_config():
    assert _call(headers={"Origin": "http://192.168.1.5:8000"},
                 extra_origins=("http://192.168.1.5:8000",)) == 200


def test_parse_extra_origins_from_env(monkeypatch):
    from web.csrf import allowed_origins_from_env
    monkeypatch.setenv("AUTOTEST_ALLOWED_ORIGINS", " http://a:1 , ,http://b:2/ ")
    assert allowed_origins_from_env() == ("http://a:1", "http://b:2")


def test_web_app_registers_csrf_middleware():
    import web.app as web_app
    assert any(m.cls is CSRFOriginMiddleware for m in web_app.app.user_middleware)
