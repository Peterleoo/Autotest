# -*- coding: utf-8 -*-
"""子进程退出码必须记录；目标达成但退出码非 0 时，失败原因应如实指向退出码"""
import subprocess
import sys

import pytest

import core.task_device_pipeline as pipeline_module
from core.task_manager import TaskManager

CHILD_SCRIPT = (
    "import sys\n"
    "print('2026-11-04 15:00:00,000 [WARNING] Antigravity 官方直连网络抖动 (ConnectionResetError(10054))，正在等待 1.5s 自动重试 (1/3)...')\n"
    "print('2026-11-04 15:00:05,000 [INFO] 🎉 目标完成并通过 DSH 独立核验门禁: 已完成')\n"
    "print('2026-11-04 15:00:05,100 [INFO] 原生 ADB 会话结束')\n"
    "sys.exit({code})\n"
)


def _run(monkeypatch, exit_code):
    real_popen = subprocess.Popen

    def fake_popen(cmd, **kwargs):
        return real_popen([sys.executable, "-c", CHILD_SCRIPT.format(code=exit_code)], **kwargs)

    monkeypatch.setattr(pipeline_module.subprocess, "Popen", fake_popen)
    mgr = TaskManager()
    monkeypatch.setattr(mgr, "_save_session", lambda sid: None)
    sid = f"sess_unit_exitcode_{exit_code}"
    session = {
        "session_id": sid, "status": "RUNNING", "is_systemic_suite": True,
        "plan_steps": [{"step_id": 1, "title": "唯一步骤", "status": "RUNNING"}],
        "devices": {}, "timeline_blocks": [],
    }
    dev_state = {"logs": [], "status": "RUNNING", "action": ""}
    mgr.sessions[sid] = session
    try:
        mgr._run_real_android_pipeline(session, dev_state, "fake_dev", "目标", "case", 0.0)
    finally:
        mgr.sessions.pop(sid, None)
    return session, dev_state


def test_exit_code_is_logged_on_success(monkeypatch):
    session, dev_state = _run(monkeypatch, 0)
    assert any("测试子进程退出码: 0" in l for l in dev_state["logs"])
    assert session.get("is_success") is True


def test_nonzero_exit_with_goal_achieved_reports_exit_code(monkeypatch):
    session, dev_state = _run(monkeypatch, 3)
    assert any("测试子进程退出码: 3" in l for l in dev_state["logs"])
    assert session.get("is_success") is False
    assert session["error_type"] == "CHILD_EXIT_NONZERO"
    assert "退出码 3" in session["error_message"]
    assert "ConnectionResetError" not in session["error_message"]
