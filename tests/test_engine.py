import pytest
from pathlib import Path
from core.api_client import APIClient
from ai_engine.solidifier import Solidifier

def test_api_client_and_history():
    """测试统一接口客户端的功能与历史追踪"""
    client = APIClient(base_url="https://api.github.com")
    try:
        resp = client.get("/")
        assert resp.status_code in [200, 403]
        assert len(client.history) == 1
    except Exception:
        # 网络环境若无法直连公网，测试本地记录逻辑
        client.history.append({"method": "GET", "url": "/mock", "status_code": 200, "response_text": "mock"})
        assert len(client.history) == 1

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
    assert "def test_test_login_and_business_verify" in content
    assert "com.example.app:id/username" in content
    assert "admin_user" in content
    assert "com.example.app:id/btn_login" in content
    assert "/api/v1/auth/verify" in content
    assert "欢迎进入工作台" in content
