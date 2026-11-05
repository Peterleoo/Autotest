# -*- coding: utf-8 -*-
"""人机协同决策执行失败时必须消费决策文件并退出，不得每秒重放同一决策（重复填验证码/点登录）"""
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from ai_engine.test_agent import AITestAgent

ROOT = Path(__file__).resolve().parent.parent

SMS_DECISION = {
    "action": "request_human_help",
    "help_type": "input",
    "title": "请输入短信验证码",
    "fields": [{"key": "sms_code", "label": "短信验证码", "target_index": 3}],
}
SMS_SCREEN = {
    "elements": [
        {"index": 1, "text": "手机号登录"},
        {"index": 3, "text": "请输入验证码", "is_input": True},
        {"index": 4, "text": "确定登录"},
    ]
}


def _write_later(path: Path, payload: dict, delay: float = 0.1) -> threading.Thread:
    def _run() -> None:
        time.sleep(delay)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    t = threading.Thread(target=_run)
    t.start()
    return t


def test_execution_error_consumes_decision_and_returns_false():
    agent = AITestAgent(driver=MagicMock(), app_identifier="demo_app", session_id="sess_hitl_fail_once")
    decision_file = ROOT / "scratch" / f"decision_{agent.session_id}.json"
    calls = []

    def boom(code, screen):
        calls.append(code)
        raise RuntimeError("adb disconnected")

    agent._execute_sms_code_injection = boom
    t = _write_later(decision_file, {"status": "RESOLVED", "decision_type": "ai_submit",
                                     "inputs": {"sms_code": "111222"}})
    started = time.time()
    res = agent._handle_ai_requested_human_help(SMS_DECISION, SMS_SCREEN, "登录", max_wait_seconds=5)
    t.join()

    assert res is False
    assert calls == ["111222"], f"决策只应执行一次，实际执行 {len(calls)} 次"
    assert not decision_file.exists(), "失败的决策文件必须被消费，避免重放"
    assert time.time() - started < 4, "执行失败应立即退出等待，而不是等到超时"


def test_malformed_decision_file_is_retried_not_consumed():
    """半写入的 JSON 应在下一轮重读，而不是被当成失败丢弃"""
    agent = AITestAgent(driver=MagicMock(), app_identifier="demo_app", session_id="sess_hitl_partial")
    decision_file = ROOT / "scratch" / f"decision_{agent.session_id}.json"
    agent._execute_sms_code_injection = MagicMock(return_value=True)

    def _partial_then_full() -> None:
        time.sleep(0.1)
        decision_file.parent.mkdir(parents=True, exist_ok=True)
        decision_file.write_text('{"status": "RES', encoding="utf-8")
        time.sleep(1.5)
        decision_file.write_text(json.dumps({"status": "RESOLVED", "decision_type": "manual_done"}),
                                 encoding="utf-8")

    t = threading.Thread(target=_partial_then_full)
    t.start()
    res = agent._handle_ai_requested_human_help(SMS_DECISION, SMS_SCREEN, "登录", max_wait_seconds=8)
    t.join()

    assert res is True
    assert not decision_file.exists()
