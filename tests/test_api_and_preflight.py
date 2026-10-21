import json
import urllib.request
import pytest

BASE_URL = "http://127.0.0.1:8000"

def _get_json(endpoint: str):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "Autotest-TestSuite/1.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))

def test_system_preflight_contract():
    """验证前置全景巡检接口契约规范"""
    data = _get_json("/api/system/preflight")
    assert data["success"] is True
    assert "ready" in data
    assert "missing" in data
    assert "checks" in data
    
    checks = data["checks"]
    assert "ai" in checks
    assert "app" in checks
    assert "device" in checks
    
    # 验证三大节点结构
    assert "ready" in checks["ai"]
    assert "provider" in checks["ai"]
    assert "ready" in checks["app"]
    assert "ready" in checks["device"]

def test_apps_endpoint():
    """验证待测应用列表接口"""
    data = _get_json("/api/apps")
    assert "apps" in data
    assert isinstance(data["apps"], list)

def test_devices_endpoint():
    """验证设备感知接口"""
    data = _get_json("/api/devices")
    assert "android_devices" in data
    assert "ios_node" in data

def test_solidified_cases_endpoint():
    """验证固化测试资产看板列表接口"""
    data = _get_json("/api/solidified_cases")
    assert "cases" in data
    assert isinstance(data["cases"], list)
    assert len(data["cases"]) > 0
