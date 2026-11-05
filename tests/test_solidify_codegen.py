# -*- coding: utf-8 -*-
"""P0-1 固化脚本生成正确性：语法合法、真实断言、无动作拒绝固化"""
import ast
import asyncio

import pytest

from ai_engine.solidifier import Solidifier
from ai_engine.verifier import TaskVerifier
from config.settings import settings
from web.app import task_mgr, save_session_to_local_case


@pytest.fixture(autouse=True)
def _isolate_side_effects(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SOLIDIFIED_DIR", tmp_path)
    monkeypatch.setattr(task_mgr, "_save_session", lambda sid: None)
    from core.deliverables_manager import deliverables_mgr
    monkeypatch.setattr(deliverables_mgr, "register_test_script", lambda **kw: None)


def _make_session(sid, actions, anchors=None):
    session = {
        "session_id": sid,
        "goal": "进入'我的'页面并检查\"设置\"入口",
        "title": "我的页面",
        "plan_steps": [],
        "timeline_blocks": [{"type": "step_execution", "actions": actions}],
    }
    if anchors is not None:
        session["final_anchor_texts"] = anchors
    task_mgr.sessions[sid] = session
    return session


def test_generated_script_parses_with_quotes_and_newlines(tmp_path):
    path = Solidifier.solidify_test_case(
        case_name="quotes",
        goal='目标含 \'单引号\' 与 "双引号" 以及 """三引号""" \\ 反斜杠',
        action_history=[
            {"action": "tap", "reason": "点击【It's me】\nimport os", "locator": {"by": "coordinates", "value": "10,20", "text": "It's me"}},
            {"action": "type", "reason": "输入", "text": "O'Brien\n"},
            {"action": "swipe", "direction": "up'"},
            {"action": "assert_text", "expected": "我's 页面"},
            {"action": "call_api", "method": "GET", "endpoint": "/a'b", "json": {"k": "v'"}},
        ],
        output_dir=tmp_path,
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "\nimport os" not in source
    asserted = [n.test.left.value for n in ast.walk(tree) if isinstance(n, ast.Assert) and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Constant)]
    assert "我's 页面" in asserted


def test_extract_final_anchor_texts_prefers_bottom_native_texts():
    screen = {"elements": [
        {"text": "首页", "center": (100, 2100), "bounds": "[0,2050][200,2150]"},
        {"text": "我的", "center": (900, 2100), "bounds": "[800,2050][1000,2150]"},
        {"text": "12:30", "center": (50, 20), "bounds": "[0,0][100,40]"},
        {"text": "OCR文字", "center": (500, 2140)},
        {"text": "这是一段非常非常长的推荐房源描述文字", "center": (500, 800), "bounds": "[0,700][1080,900]"},
        {"text": "推荐", "center": (500, 300), "bounds": "[400,250][600,350]"},
    ]}
    anchors = TaskVerifier.extract_final_anchor_texts(screen, limit=3)
    assert anchors[:2] == ["首页", "我的"] or anchors[:2] == ["我的", "首页"]
    assert "OCR文字" not in anchors and "12:30" not in anchors
    assert anchors[2] == "推荐"


def test_save_rejects_session_without_actions():
    sid = "sess_unit_p01_noact"
    _make_session(sid, actions=[{"type": "ocr"}])
    try:
        data = asyncio.run(save_session_to_local_case(sid))
        assert data["success"] is False
    finally:
        task_mgr.sessions.pop(sid, None)


def test_save_uses_observed_anchor_and_tap_text(tmp_path):
    sid = "sess_unit_p01_anchor"
    actions = [{
        "type": "tap", "desc": "点击同意按钮", "target": "我同意",
        "element_text": "我同意", "element_id": "com.demo:id/agree", "param": "tap(660, 2064)",
    }]
    _make_session(sid, actions, anchors=["首页", "我的"])
    try:
        data = asyncio.run(save_session_to_local_case(sid))
        assert data["success"] is True and data["missing_assertion"] is False
        source = next(tmp_path.rglob(data["filename"])).read_text(encoding="utf-8")
        ast.parse(source)
        assert "text='我同意'" in source and "res_id='com.demo:id/agree'" in source
        assert "assert '首页' in driver.page_source" in source
        assert "进入'我的'页面" not in source.split("def test_", 1)[1].split('"""', 2)[2]
    finally:
        task_mgr.sessions.pop(sid, None)


def test_save_marks_missing_assertion_without_anchors(tmp_path):
    sid = "sess_unit_p01_noanchor"
    actions = [{"type": "tap", "desc": "点击某处", "target": "点击某处", "param": "tap(1, 2)"}]
    _make_session(sid, actions)
    try:
        data = asyncio.run(save_session_to_local_case(sid))
        assert data["success"] is True and data["missing_assertion"] is True
        source = next(tmp_path.rglob(data["filename"])).read_text(encoding="utf-8")
        assert "page_source" not in source.split("def test_", 1)[1]
        assert "text=None" in source  # AI 动作描述不应被当作控件文字
    finally:
        task_mgr.sessions.pop(sid, None)
