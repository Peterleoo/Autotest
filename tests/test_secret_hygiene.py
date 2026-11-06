# -*- coding: utf-8 -*-
"""公开仓库凭据卫生：源码不得包含 OAuth 凭据；模型桥接服务不得对局域网无鉴权开放"""
import base64
import re
import subprocess
from pathlib import Path

import asyncio

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _enable_antigravity(monkeypatch):
    """本文件测试凭据/桥接自身行为，需在开关开启的前提下运行"""
    monkeypatch.setenv("ANTIGRAVITY_ENABLED", "true")
SECRET_PATTERNS = [
    re.compile(r"GOCSPX-[A-Za-z0-9_-]{10,}"),            # Google OAuth client secret
    re.compile(r"ya29\.[A-Za-z0-9_-]{20,}"),             # Google access token
    re.compile(r"1//0[A-Za-z0-9_-]{30,}"),               # Google refresh token
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),               # Google API key
]
B64_TOKEN = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


def _tracked_source_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / f for f in out.splitlines() if f.endswith((".py", ".js", ".html", ".json", ".md", ".example"))]


def _contains_secret(text: str) -> bool:
    if any(p.search(text) for p in SECRET_PATTERNS):
        return True
    for m in B64_TOKEN.finditer(text):  # base64 混淆同样视为泄露
        try:
            decoded = base64.b64decode(m.group(0) + "==", validate=False).decode("utf-8", "ignore")
        except Exception:
            continue
        if any(p.search(decoded) for p in SECRET_PATTERNS):
            return True
    return False


def test_no_oauth_secrets_in_tracked_sources():
    offenders = [str(p.relative_to(ROOT)) for p in _tracked_source_files()
                 if p.exists() and _contains_secret(p.read_text(encoding="utf-8", errors="ignore"))]
    assert offenders == []


def test_missing_client_credentials_fail_with_guidance(monkeypatch):
    from core import antigravity_credentials as cred
    monkeypatch.delenv(cred.CLIENT_ID_ENV, raising=False)
    monkeypatch.delenv(cred.CLIENT_SECRET_ENV, raising=False)
    with pytest.raises(cred.AntigravityCredentialsMissing, match=".env"):
        cred.get_client_credentials()


@pytest.fixture
def bridge(monkeypatch):
    import importlib
    import tools.antigravity_bridge as mod
    return importlib.reload(mod)


def test_bridge_binds_localhost_by_default(monkeypatch, bridge):
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_HOST", raising=False)
    import importlib
    mod = importlib.reload(bridge)
    assert mod.BRIDGE_HOST == "127.0.0.1"


def _get_status(app, path, headers=None):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {
        "type": "http", "method": "GET", "path": path, "raw_path": path.encode(), "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "server": ("127.0.0.1", 19387), "client": ("127.0.0.1", 5555), "scheme": "http",
        "http_version": "1.1", "root_path": "",
    }
    asyncio.run(app(scope, receive, send))
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def test_bridge_rejects_requests_without_key(monkeypatch, bridge):
    monkeypatch.setattr(bridge, "BRIDGE_KEY", "s3cret")
    assert _get_status(bridge.app, "/health") == 401
    assert _get_status(bridge.app, "/health", {"Authorization": "Bearer wrong"}) == 401
    assert _get_status(bridge.app, "/health", {"Authorization": "Bearer s3cret"}) == 200


def test_bridge_open_locally_when_no_key(monkeypatch, bridge):
    monkeypatch.setattr(bridge, "BRIDGE_KEY", "")
    assert _get_status(bridge.app, "/health") == 200


def test_oauth_state_works_without_client_credentials(monkeypatch):
    """新部署的用户还没配置 .env 时，查询状态/配置接口不能报错，只有真正登录时才提示配置"""
    from core import antigravity_credentials as cred
    from core.antigravity_oauth import AntigravityOAuth
    monkeypatch.delenv(cred.CLIENT_ID_ENV, raising=False)
    monkeypatch.delenv(cred.CLIENT_SECRET_ENV, raising=False)

    oauth = AntigravityOAuth()
    assert isinstance(oauth.get_state(), dict)
    with pytest.raises(cred.AntigravityCredentialsMissing):
        _ = oauth.client_secret
