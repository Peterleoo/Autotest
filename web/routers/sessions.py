# -*- coding: utf-8 -*-
"""测试会话生命周期接口"""
from fastapi import APIRouter
import json
from typing import Optional, Dict, Any
from fastapi import Form, Body
from fastapi.responses import JSONResponse
from core.report_generator import ReportGenerator

from web.shared import (
    logger,
    task_mgr,
)

router = APIRouter()


@router.post("/api/sessions/{session_id}/resolve_decision")
async def resolve_session_decision(session_id: str, payload: Dict[str, Any] = Body(...)):
    """人机协同：接收用户的凭证注入/投屏手动完成/跳过决策"""
    success = task_mgr.resolve_decision(session_id, payload)
    return {"success": success}


# ==================== 多任务并发会话与多设备协同中心 (Codex Sessions) ====================

@router.get("/api/sessions")
async def get_sessions_list():
    """获取所有任务会话列表"""
    return {"sessions": task_mgr.list_sessions(), "active_id": task_mgr.active_session_id}


@router.post("/api/sessions/create")
async def create_task_session(
    goal: str = Form(...),
    devices: str = Form("auto"),
    test_mode: str = Form("real"),
    case_name: str = Form("auto_flow"),
    approval_mode: str = Form("auto"),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    app_filename: Optional[str] = Form(None),
    app_package: Optional[str] = Form(None),
    app_label: Optional[str] = Form(None),
    app_activity: Optional[str] = Form(None),
    app_id: Optional[str] = Form(None),
    attachments: Optional[str] = Form(None)
):
    """创建新任务会话并向所选设备分发并发执行，支持自动放行与人工审批确认，支持动态指定模型与多模态需求附件"""
    device_ids = []
    if devices and devices != "auto":
        device_ids = [d.strip() for d in devices.split(",") if d.strip()]
    
    parsed_attachments = None
    if attachments:
        try:
            parsed_attachments = json.loads(attachments)
            if not isinstance(parsed_attachments, list):
                parsed_attachments = None
        except Exception:
            parsed_attachments = None

    session_id = task_mgr.create_session(
        goal=goal,
        device_ids=device_ids,
        test_mode=test_mode,
        case_name=case_name,
        approval_mode=approval_mode,
        provider=provider,
        model=model,
        app_filename=app_filename,
        app_package=app_package,
        app_label=app_label,
        app_activity=app_activity,
        app_id=app_id,
        attachments=parsed_attachments
    )
    return {"success": True, "session_id": session_id, "message": "测试会话已创建"}


@router.post("/api/sessions/{session_id}/approve")
async def approve_task_session(session_id: str):
    """人工审批通过：放行并唤醒向各设备分发测试"""
    ok = task_mgr.approve_session(session_id)
    if ok:
        return {"success": True, "message": "人工审批已通过，多端测试开始协同推进！"}
    return {"success": False, "message": "审批放行失败或会话非待审批状态"}


@router.post("/api/sessions/{session_id}/clarify")
async def clarify_task_session(session_id: str, account: str = Form(""), env: str = Form("生产")):
    """用户在中间流提交测试前置补充参数并继续执行"""
    inputs = {"account": account, "env": env}
    ok = task_mgr.clarify_session(session_id, inputs)
    return {"success": ok, "message": "前置参数已补充，测试流程继续流转"}


@router.get("/api/sessions/{session_id}/raw_logs")
async def get_session_raw_logs_endpoint(session_id: str):
    """获取指定会话的全量真实底层执行日志文本 (支持全貌查看与原汁原味排查)"""
    from fastapi.responses import PlainTextResponse
    logs_text = task_mgr.get_session_raw_logs(session_id)
    return PlainTextResponse(logs_text, media_type="text/plain; charset=utf-8")


@router.get("/api/sessions/{session_id}")
async def get_session_detail(session_id: str, offsets: Optional[str] = None):
    """获取指定测试会话的多设备实时进度与增量日志"""
    offset_dict = {}
    if offsets:
        try:
            offset_dict = json.loads(offsets)
        except Exception:
            logger.debug("忽略异常 @ get_session_detail", exc_info=True)
    detail = task_mgr.get_session(session_id, offset_dict)
    if detail:
        return detail
    return JSONResponse(status_code=404, content={"message": "会话不存在"})


@router.post("/api/sessions/{session_id}/pause")
async def pause_task_session(session_id: str):
    """用户主动暂停正在运行中的测试任务"""
    ok = task_mgr.pause_session(session_id)
    return {"success": ok, "message": "测试任务已暂停" if ok else "无法暂停（任务非运行状态或已结束）"}


@router.post("/api/sessions/{session_id}/resume")
async def resume_task_session(session_id: str):
    """用户主动恢复继续已暂停的测试任务"""
    ok = task_mgr.resume_session(session_id)
    return {"success": ok, "message": "测试任务已恢复推进" if ok else "无法恢复（任务非暂停状态）"}


@router.post("/api/sessions/{session_id}/stop")
async def stop_task_session(session_id: str):
    """用户主动彻底终止当前正在运行的测试任务"""
    ok = task_mgr.stop_session(session_id)
    return {"success": ok, "message": "测试任务已彻底终止" if ok else "终止失败或任务不存在"}


@router.post("/api/sessions/{session_id}/delete")
async def delete_task_session(session_id: str):
    """删除指定的测试会话记录"""
    ok = task_mgr.delete_session(session_id)
    return {"success": ok}


@router.post("/api/sessions/{session_id}/rename")
async def rename_session(session_id: str, payload: Dict[str, Any] = Body(...)):
    """重命名测试会话标题"""
    new_title = (payload.get("title") or "").strip()
    if not new_title:
        return JSONResponse({"success": False, "error": "标题不能为空"})
    session = task_mgr.sessions.get(session_id)
    if not session:
        return JSONResponse({"success": False, "error": "会话不存在"})
    session["title"] = new_title
    task_mgr._save_session(session_id)
    return JSONResponse({"success": True, "title": new_title})


@router.post("/api/sessions/{session_id}/force_run_doc_suite")
async def force_run_doc_suite(session_id: str):
    """用户在确认知情后，忽略相关性不匹配提示，强制按文档生成用例并在当前应用上执行"""
    success = task_mgr.force_resume_doc_suite(session_id)
    if not success:
        return JSONResponse(status_code=400, content={"success": False, "message": "会话不存在或未找到文档附件"})
    return {"success": True, "message": "已强制放行，正在为您提炼用例并驱动真机测试"}


@router.post("/api/sessions/{session_id}/message")
async def append_session_message(
    session_id: str,
    message: str = Form(...),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    app_filename: Optional[str] = Form(None),
    app_package: Optional[str] = Form(None),
    app_label: Optional[str] = Form(None),
    app_activity: Optional[str] = Form(None),
    attachments: Optional[str] = Form(None)
):
    """在已有单条任务会话中进行多轮连续对话，支持打断纠偏与追加测试意图，支持动态切换模型与多模态附件"""
    try:
        parsed_attachments = None
        if attachments:
            try:
                parsed_attachments = json.loads(attachments)
                if not isinstance(parsed_attachments, list):
                    parsed_attachments = None
            except Exception:
                parsed_attachments = None

        res = task_mgr.append_session_message(session_id, message, provider=provider, model=model, attachments=parsed_attachments)
        return res
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})


@router.post("/api/sessions/{session_id}/accept")
async def accept_session(session_id: str):
    """用户正式验收通过当前任务交付物并封板归档 (对标 PM-product Accept 规范)"""
    try:
        res = task_mgr.accept_session(session_id)
        return res
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})


@router.post("/api/sessions/{session_id}/rework")
async def rework_session(session_id: str, note: str = Form(...)):
    """用户打回返工：携带明确返工项原地恢复执行 (对标 PM-product Rework 规范)"""
    try:
        res = task_mgr.rework_session(session_id, note)
        return res
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})


@router.post("/api/sessions/{session_id}/compact")
async def compact_session(session_id: str):
    """主动执行会话历史上下文压缩 (/compact)，释放 50%+ 冗余日志，浓缩事实状态机"""
    try:
        res = task_mgr.compact_session_context(session_id)
        return {"success": True, "result": res}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})


@router.get("/api/sessions/{session_id}/deliverables")
async def get_session_deliverables(session_id: str):
    """获取当前会话的全景测试交付物矩阵 (Pytest脚本/截图/HTML报告)"""
    try:
        session = task_mgr.get_session(session_id)
        if not session:
            return JSONResponse(status_code=404, content={"error": "会话不存在"})
        delivs = session.get("deliverables") or task_mgr.register_deliverables(session_id)
        return {"session_id": session_id, "deliverables": delivs}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@router.get("/api/sessions/{session_id}/token_pressure")
async def get_session_token_pressure(session_id: str):
    """获取当前会话的实时 Token 水位与监控状态"""
    try:
        from core.memory_manager import MemoryManager
        session = task_mgr.get_session(session_id)
        if not session:
            return JSONResponse(status_code=404, content={"error": "会话不存在"})
        ctx = MemoryManager.build_memory_context(session)
        est_tokens = MemoryManager.estimate_tokens(ctx) + len(session.get("plan_steps", [])) * 120
        status = MemoryManager.get_token_pressure_status(est_tokens)
        return {"session_id": session_id, "token_pressure": status}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@router.get("/api/sessions/{session_id}/compatibility_matrix")
async def get_session_compatibility_matrix(session_id: str):
    """获取当前会话的多机型视觉差异与步骤对齐对比看板 (Multi-Device Visual Diff Matrix)"""
    try:
        session = task_mgr.get_session(session_id)
        if not session:
            return JSONResponse(status_code=404, content={"error": "会话不存在"})
        from core.report_generator import ReportGenerator
        matrix = ReportGenerator.generate_compatibility_matrix(session)
        return matrix
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
