# -*- coding: utf-8 -*-
"""P1-5 真机优先：无设备时直接报错，不得隐式退化为 mock_device"""
import asyncio
import json

import pytest

from core.app_manager import AppManager
from web.app import task_mgr, run_systemic_test_suite

SUITE = {"suite_title": "无设备套件", "cases": [{"id": "tc-01", "title": "用例1", "goal": "g", "assert_rule": "a"}]}
SID = "sess_unit_p15_nodev"


@pytest.fixture
def no_devices(monkeypatch):
    monkeypatch.setattr(AppManager, "get_connected_devices", lambda self: [])
    monkeypatch.setattr(task_mgr, "_save_session", lambda sid: None)


def test_run_suite_without_device_raises_and_creates_no_session(no_devices):
    before = set(task_mgr.sessions)
    with pytest.raises(ValueError, match="真机设备"):
        task_mgr.run_systemic_suite(session_id=None, suite_data=dict(SUITE))
    assert set(task_mgr.sessions) == before


def test_run_suite_endpoint_returns_400_without_device(no_devices):
    resp = asyncio.run(run_systemic_test_suite({"suite_data": dict(SUITE)}))
    assert resp.status_code == 400
    assert "真机设备" in json.loads(resp.body)["message"]


def test_suite_runner_fails_session_when_no_target_device(no_devices):
    task_mgr.sessions[SID] = {"session_id": SID, "status": "RUNNING", "target_devices": [], "devices": {}}
    try:
        task_mgr._systemic_suite_runner(SID, SUITE["cases"], keep_state=True)
        sess = task_mgr.sessions[SID]
        assert sess["status"] == "FAILED"
        assert "真机设备" in sess["error_message"]
        assert "mock_device" not in sess["devices"]
    finally:
        task_mgr.sessions.pop(SID, None)
