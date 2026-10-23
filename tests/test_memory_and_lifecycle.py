# -*- coding: utf-8 -*-
"""
自动化测试用例：多轮对话记忆、端侧事实状态机、待验收与返工闭环、全景交付物注册与 Token 治理
"""
import pytest
from core.memory_manager import MemoryManager
from core.task_manager import TaskManager


def test_fact_memory_and_turn_model():
    """验证多轮 Turn 数据模型与端侧事实状态机正常流转"""
    session = {
        "session_id": "sess_test_turn_1",
        "goal": "打开象盒找房进入买房首页",
        "app_package": "com.apicloud.A6995433058179",
        "status": "COMPLETED",
        "plan_steps": [
            {"step_id": 1, "title": "启动应用", "status": "COMPLETED"},
            {"step_id": 2, "title": "进入买房页", "status": "COMPLETED"}
        ]
    }

    # 1. 确保旧会话平滑兼容为 Turns
    turns = MemoryManager.ensure_session_turns(session)
    assert len(turns) == 1
    assert turns[0]["turn_id"] == 1
    assert turns[0]["user_message"] == "打开象盒找房进入买房首页"

    # 2. 模拟第 2 轮用户追加指令
    t2 = MemoryManager.create_turn(2, "查看第2个房源详情并截图")
    turns.append(t2)
    MemoryManager.update_fact_memory(
        session,
        current_package="com.apicloud.A6995433058179",
        milestone="已进入买房列表页",
        page_summary="买房列表页，当前展示房源列表"
    )

    # 3. 验证记忆上下文生成
    ctx = MemoryManager.build_memory_context(session)
    assert "com.apicloud.A6995433058179" in ctx
    assert "已进入买房列表页" in ctx
    assert "查看第2个房源详情并截图" in ctx
    assert "严禁退回桌面盲目重新冷启动" in ctx

    # 4. 验证 Token 估算与压力
    tokens = MemoryManager.estimate_tokens(ctx)
    pressure = MemoryManager.get_token_pressure_status(tokens, 1000000)
    assert pressure["level"] == "normal"
    assert pressure["percentage"] < 1.0


def test_rework_and_accept_lifecycle():
    """验证任务生命周期的待验收 (READY_FOR_REVIEW)、打回返工 (Rework) 与验收 (Accept) 闭环"""
    task_mgr = TaskManager()
    session_id = "sess_lifecycle_test_unit"

    session = {
        "session_id": session_id,
        "goal": "测试找房搜索流程",
        "status": "READY_FOR_REVIEW",
        "is_success": True,
        "plan_steps": [{"step_id": 1, "title": "搜索房源", "status": "COMPLETED"}],
        "devices": {},
        "target_devices": []
    }
    task_mgr.sessions[session_id] = session

    # 1. 用户要求打回返工
    rework_res = task_mgr.rework_session(session_id, "筛选条件改为总价200万以下")
    assert rework_res["success"] is True
    assert session["status"] == "RUNNING"
    assert len(session["turns"]) == 2
    assert session["turns"][-1]["is_rework"] is True
    assert "总价200万以下" in session["turns"][-1]["rework_note"]

    # 2. 模拟执行完成后再次进入 READY_FOR_REVIEW
    session["status"] = "READY_FOR_REVIEW"
    session["turns"][-1]["status"] = "READY_FOR_REVIEW"

    # 3. 用户正式验收通过
    accept_res = task_mgr.accept_session(session_id)
    assert accept_res["success"] is True
    assert session["status"] == "COMPLETED"
    assert session["is_success"] is True
    assert "accepted_at" in session


def test_deliverables_and_compaction():
    """验证交付物注册与上下文压缩"""
    task_mgr = TaskManager()
    session_id = "sess_compaction_unit"

    session = {
        "session_id": session_id,
        "goal": "长测试链路验证",
        "status": "COMPLETED",
        "turns": [
            {"turn_id": 1, "user_message": "第1步", "conclusion": "已完成第1阶段", "plan_steps": [{"raw_logs": "huge log 123"}]},
            {"turn_id": 2, "user_message": "第2步", "conclusion": "已完成第2阶段", "plan_steps": [{"raw_logs": "huge log 456"}]},
            {"turn_id": 3, "user_message": "最新第3步", "conclusion": "", "plan_steps": [{"raw_logs": "active log"}]}
        ],
        "fact_memory": MemoryManager.create_empty_fact_memory()
    }
    task_mgr.sessions[session_id] = session

    # 1. 验证上下文压缩
    compact_res = task_mgr.compact_session_context(session_id)
    assert compact_res["compacted"] is True
    assert compact_res["turns_compacted"] == 2
    # 前序轮次的底层 raw_logs 被彻底释放清空
    assert session["turns"][0]["plan_steps"][0]["raw_logs"] == ""

    # 2. 验证交付物注册
    delivs = task_mgr.register_deliverables(session_id)
    assert isinstance(delivs, list)
