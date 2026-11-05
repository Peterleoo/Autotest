# -*- coding: utf-8 -*-
"""报告块类型更名（final_report -> report）后：读取会话不重复追加报告、自愈历史重复块、前端可找到报告"""
import pytest

from core.task_manager import TaskManager
from core.timeline_manager import TimelineManager
from tests.frontend_source import read_frontend_source

REPORT = "# 📊 移动端自动化测试交付物报告\n\n正文内容"
SID = "sess_unit_report_dedup"


@pytest.fixture
def mgr():
    m = TaskManager()
    yield m
    m.sessions.pop(SID, None)


def _session(blocks):
    return {
        "session_id": SID, "title": "报告去重", "goal": "目标", "created_at": "17:00:00",
        "status": "READY_FOR_REVIEW", "is_success": True,
        "plan_steps": [], "devices": {},
        "messages": [{"role": "assistant", "content": REPORT, "is_report": True}],
        "timeline_blocks": [TimelineManager.create_user_block("目标", turn_id=0), *blocks],
    }


def _report_blocks(m):
    return [b for b in m.sessions[SID]["timeline_blocks"] if b.get("type") in ("report", "final_report")]


def test_repeated_reads_do_not_append_duplicate_reports(mgr):
    mgr.sessions[SID] = _session([TimelineManager.create_report_block(REPORT, SID)])
    for _ in range(5):
        mgr.get_session(SID)
    assert len(_report_blocks(mgr)) == 1


def test_existing_duplicate_reports_are_self_healed(mgr):
    dupes = [TimelineManager.create_report_block(REPORT, SID) for _ in range(12)]
    mgr.sessions[SID] = _session(dupes)
    mgr.get_session(SID)
    assert len(_report_blocks(mgr)) == 1


def test_legacy_final_report_block_is_recognized(mgr):
    legacy = {**TimelineManager.create_report_block(REPORT, SID), "type": "final_report"}
    mgr.sessions[SID] = _session([legacy])
    mgr.get_session(SID)
    assert [b["type"] for b in _report_blocks(mgr)] == ["final_report"]


def test_frontend_looks_up_both_report_block_types():
    src = read_frontend_source()
    assert 'b.type === "report" || b.type === "final_report"' in src
    assert 'blk.type === "report" || blk.type === "final_report"' in src
