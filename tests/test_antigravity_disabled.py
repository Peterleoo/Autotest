# -*- coding: utf-8 -*-
"""Google 反代（Antigravity）停用开关：默认关闭；关闭时任何入口都不得读取/刷新/使用个人账号令牌"""
import asyncio
import importlib

import pytest

from core import antigravity_credentials as cred


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.delenv(cred.ENABLED_ENV, raising=False)  # 未设置即视为关闭
    yield


def test_disabled_by_default(disabled):
    assert cred.is_antigravity_enabled() is False
    with pytest.raises(cred.AntigravityDisabled):
        cred.ensure_antigravity_enabled()


@pytest.mark.parametrize("value", ["true", "1", "YES", "on"])
def test_explicit_opt_in_enables(monkeypatch, value):
    monkeypatch.setenv(cred.ENABLED_ENV, value)
    assert cred.is_antigravity_enabled() is True


def test_client_credentials_refused_when_disabled(disabled):
    with pytest.raises(cred.AntigravityDisabled):
        cred.get_client_credentials()


def test_direct_client_does_not_load_tokens_when_disabled(disabled, monkeypatch):
    from core.antigravity_direct import AntigravityDirectClient
    monkeypatch.setattr(AntigravityDirectClient, "_load_token_data",
                        lambda self: pytest.fail("停用时不得读取令牌文件"))
    with pytest.raises(cred.AntigravityDisabled):
        AntigravityDirectClient()


def test_oauth_state_hides_account_and_login_refused(disabled):
    from core.antigravity_oauth import AntigravityOAuth
    state = AntigravityOAuth().get_state()
    assert state["is_logged_in"] is False and state["disabled"] is True
    assert "@" not in state["email"]  # 不暴露绑定账号
    with pytest.raises(cred.AntigravityDisabled):
        AntigravityOAuth().start_login()


def test_llm_falls_back_to_hermes_when_disabled(disabled, monkeypatch):
    from core import llm_client as lc
    calls = []

    def fake_hermes(self, system_prompt, user_prompt, image_base64=None, memory_context=None):
        if self.provider == "hermes":
            calls.append("hermes")
            return {"action": "tap"}
        return original(self, system_prompt, user_prompt, image_base64, memory_context)

    original = lc.LLMClient.chat_decision
    monkeypatch.setattr(lc.LLMClient, "chat_decision", fake_hermes)
    client = lc.LLMClient.__new__(lc.LLMClient)
    client.provider, client.model_name, client.client = "antigravity", "gemini-2.5-flash", object()
    client.last_fallback_info, client.last_usage = None, None
    res = original(client, "sys", "user")
    assert calls == ["hermes"] and res["_fallback_info"]["fallback_provider"] == "hermes"


def test_web_endpoints_refuse_antigravity(disabled):
    from web.routers import system
    login = asyncio.run(system.start_antigravity_login())
    switch = asyncio.run(system.switch_antigravity_model(model="gemini-2.5-pro"))
    assert login.status_code == 403 and switch.status_code == 403


def test_bridge_refuses_requests_when_disabled(disabled):
    import tools.antigravity_bridge as bridge
    bridge = importlib.reload(bridge)
    from tests.test_secret_hygiene import _get_status
    assert _get_status(bridge.app, "/health") == 403
