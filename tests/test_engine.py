import pytest
from types import SimpleNamespace
from pathlib import Path
from core.api_client import APIClient
from ai_engine.solidifier import Solidifier

def test_api_client_and_history(monkeypatch):
    """测试统一接口客户端的 URL 拼接与历史追踪（mock 网络，不依赖公网）"""
    client = APIClient(base_url="https://api.example.com/")
    sent = {}

    def fake_request(method, url, timeout=None, **kwargs):
        sent.update(method=method, url=url, timeout=timeout, **kwargs)
        return SimpleNamespace(status_code=201, text="ok" * 600,
                               request=SimpleNamespace(headers={"X-Test": "1"}))

    monkeypatch.setattr(client.session, "request", fake_request)
    resp = client.post("/v1/items", json={"name": "a"}, timeout=3)

    assert resp.status_code == 201
    assert sent["method"] == "POST" and sent["url"] == "https://api.example.com/v1/items"
    assert sent["timeout"] == 3 and sent["json"] == {"name": "a"}
    assert len(client.history) == 1
    record = client.history[0]
    assert record["status_code"] == 201 and record["endpoint"] == "/v1/items"
    assert record["json"] == {"name": "a"} and record["headers"] == {"X-Test": "1"}
    assert len(record["response_text"]) == 1000

def test_solidifier_script_generation(tmp_path):
    """测试固化引擎：将模拟的登录与业务动作轨迹固化为 Pytest 脚本"""
    mock_history = [
        {
            "action": "type",
            "reason": "输入测试账号",
            "locator": {"by": "id", "value": "com.example.app:id/username"},
            "text": "admin_user"
        },
        {
            "action": "type",
            "reason": "输入测试密码",
            "locator": {"by": "id", "value": "com.example.app:id/password"},
            "text": "123456"
        },
        {
            "action": "tap",
            "reason": "点击登录按钮",
            "locator": {"by": "id", "value": "com.example.app:id/btn_login"}
        },
        {
            "action": "call_api",
            "reason": "验证登录鉴权接口状态",
            "method": "POST",
            "endpoint": "/api/v1/auth/verify",
            "json": {"username": "admin_user"},
            "expected_status": 200
        },
        {
            "action": "assert_text",
            "reason": "断言是否进入应用首页",
            "expected": "欢迎进入工作台"
        }
    ]

    generated_file = Solidifier.solidify_test_case(
        case_name="login_and_business_verify",
        goal="测试登录业务流并验证后端鉴权接口",
        action_history=mock_history,
        output_dir=tmp_path
    )

    assert generated_file.exists()
    content = generated_file.read_text(encoding="utf-8")
    assert "def test_login_and_business_verify" in content
    assert "com.example.app:id/username" in content
    assert "admin_user" in content
    assert "com.example.app:id/btn_login" in content
    assert "/api/v1/auth/verify" in content
    assert "欢迎进入工作台" in content
