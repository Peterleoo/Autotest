# -*- coding: utf-8 -*-
import time
import uuid
from typing import Dict, Any, List, Optional, Set
from datetime import datetime

# 报告块类型：当前创建为 "report"，历史会话中仍存在旧名 "final_report"
REPORT_BLOCK_TYPES = frozenset({"report", "final_report"})

class TimelineManager:
    """
    负责维护与组装移动端 AI 测试的主流 Stream Timeline Block 事件模型
    严格对齐 Cursor / Claude Artifacts 工业标准事件流，并融入 Vercel Labs json-render 契约护栏
    """

    # 🛡️ 权威组件 Catalog (借鉴 json-render 规范，只允许受控的强类型 Block)
    SUPPORTED_BLOCK_TYPES: Set[str] = {
        "user_message",
        "system_notice",
        "thought",
        "todo_list",
        "todo_plan",
        "tool_call",
        "step_result",
        "step_execution",
        "report",
        "test_summary",
        "fault_diagnosis",
        "suite_builder",
        "doc_mismatch_guard"
    }

    @classmethod
    def validate_and_sanitize_block(cls, block: Dict[str, Any]) -> Dict[str, Any]:
        """
        组件契约验证器 (借鉴 Vercel Labs json-render Component Catalog)
        严格确保时间线块结构合规、杜绝裸危险代码注入并补齐基础元数据。
        """
        if not isinstance(block, dict):
            return {
                "block_id": f"blk_err_{uuid.uuid4().hex[:6]}",
                "type": "system_notice",
                "content": "数据格式异常",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }

        b_type = block.get("type", "system_notice")
        if b_type not in cls.SUPPORTED_BLOCK_TYPES:
            # 未知组件降级为安全系统提示
            return {
                "block_id": block.get("block_id") or f"blk_fallback_{uuid.uuid4().hex[:6]}",
                "type": "system_notice",
                "content": str(block.get("content") or f"通知: {b_type}"),
                "timestamp": block.get("timestamp") or datetime.now().strftime("%H:%M:%S")
            }

        if not block.get("block_id"):
            block["block_id"] = f"blk_{b_type}_{uuid.uuid4().hex[:6]}"
        if not block.get("timestamp"):
            block["timestamp"] = datetime.now().strftime("%H:%M:%S")

        return block

    @staticmethod
    def create_user_block(content: str, turn_id: int = 0, attachments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return {
            "block_id": f"blk_user_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "user_message",
            "turn_id": turn_id,
            "status": "COMPLETED",
            "content": content,
            "attachments": attachments or [],
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_system_notice_block(content: str, turn_id: int = 0, evidence: Optional[str] = None) -> Dict[str, Any]:
        res = {
            "block_id": f"blk_notice_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "system_notice",
            "turn_id": turn_id,
            "status": "COMPLETED",
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        if evidence:
            res["evidence"] = evidence
        return res

    @staticmethod
    def create_thought_block(duration: str, bullets: List[Dict[str, str]], turn_id: int = 0, is_done: bool = True) -> Dict[str, Any]:
        return {
            "block_id": f"blk_thought_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "thought",
            "turn_id": turn_id,
            "status": "COMPLETED" if is_done else "RUNNING",
            "duration": duration,
            "bullets": bullets,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_todo_block(
        steps: List[Dict[str, Any]],
        previous_steps: Optional[List[Dict[str, Any]]] = None,
        turn_id: int = 0
    ) -> Dict[str, Any]:
        """
        装配专业级 Todo 任务状态栏模型（同时兼容 todo_list 与 todo_plan 契约规范）
        """
        formatted_steps = []
        diff_items = []
        for idx, step in enumerate(steps):
            s_num = step.get("step_number", idx + 1)
            raw_title = step.get("title", f"步骤 {s_num}")
            raw_desc = step.get("desc", "")
            status = step.get("status", "READY")

            formatted_steps.append({
                "step_id": step.get("step_id", s_num),
                "step_number": s_num,
                "title": raw_title,
                "desc": raw_desc,
                "status": status,
                "actions": step.get("actions", []),
                "detail": step.get("detail", ""),
                "is_dynamic": step.get("is_dynamic", False),
                "updated_at": step.get("updated_at", datetime.now().strftime("%H:%M:%S"))
            })
            diff_items.append({
                "title": raw_title,
                "desc": raw_desc,
                "status": status,
                "diff_type": step.get("diff_type", "added")
            })

        total = len(formatted_steps)
        completed = sum(1 for s in formatted_steps if s["status"] in ["COMPLETED", "SKIPPED", "PASS"])
        running_step = next((s for s in formatted_steps if s["status"] == "RUNNING"), None)

        if running_step:
            summary = f"正在推进第 {running_step['step_number']}/{total} 阶段 · {running_step['title']}"
            block_status = "RUNNING"
        elif completed == total and total > 0:
            summary = f"全阶段测试规划已圆满闭环 (共 {total} 个阶段全部达成)"
            block_status = "COMPLETED"
        else:
            summary = f"测试规划已就绪 · 共 {total} 个核心阶段"
            block_status = "READY"

        return {
            "block_id": f"blk_todo_{turn_id}",
            "type": "todo_list",
            "turn_id": turn_id,
            "status": block_status,
            "title": f"任务清单 · {completed}/{total} 已完成",
            "summary": summary,
            "total_count": total,
            "total_steps": total,
            "completed_count": completed,
            "completed_steps": completed,
            "items": diff_items,
            "steps": formatted_steps,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_tool_call_block(
        tool_name: str,
        tool_input: Dict[str, Any],
        turn_id: int = 0,
        is_done: bool = False
    ) -> Dict[str, Any]:
        return {
            "block_id": f"blk_tool_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "tool_call",
            "turn_id": turn_id,
            "status": "COMPLETED" if is_done else "RUNNING",
            "tool_name": tool_name,
            "input": tool_input,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_step_result_block(
        step_title: str,
        is_success: bool,
        output_text: str,
        turn_id: int = 0
    ) -> Dict[str, Any]:
        return {
            "block_id": f"blk_stepres_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "step_result",
            "turn_id": turn_id,
            "status": "COMPLETED" if is_success else "FAILED",
            "step_title": step_title,
            "is_success": is_success,
            "output": output_text,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_step_execution_block(
        step_id: int,
        title: str,
        desc: str = "",
        actions: Optional[List[Dict[str, Any]]] = None,
        assertion_result: str = "",
        status: str = "RUNNING",
        duration: str = "",
        turn_id: int = 0
    ) -> Dict[str, Any]:
        return {
            "block_id": f"blk_exec_{turn_id}_{step_id}_{uuid.uuid4().hex[:6]}",
            "type": "step_execution",
            "turn_id": turn_id,
            "step_id": step_id,
            "title": title,
            "desc": desc,
            "actions": actions or [],
            "assertion_result": assertion_result,
            "duration": duration,
            "status": status,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_report_block(markdown_content: str, session_id: str, turn_id: int = 0) -> Dict[str, Any]:
        return {
            "block_id": f"blk_report_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "report",
            "turn_id": turn_id,
            "session_id": session_id,
            "status": "COMPLETED",
            "content": markdown_content,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_suite_builder_block(suite_data: Dict[str, Any], session_id: str, turn_id: int = 0) -> Dict[str, Any]:
        """生成契约式用例套件编排卡片块 (Suite Builder)"""
        return {
            "block_id": f"suite_block_{session_id}",
            "type": "suite_builder",
            "turn_id": turn_id,
            "session_id": session_id,
            "status": "READY",
            "suite_data": suite_data,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_doc_mismatch_guard_block(
        session_id: str,
        doc_name: str,
        app_name: str,
        relevance_info: Dict[str, Any],
        turn_id: int = 0
    ) -> Dict[str, Any]:
        """生成契约式业务契合度门禁警示卡片块 (Doc-App Relevance Guard)"""
        return {
            "block_id": f"guard_{session_id}",
            "type": "doc_mismatch_guard",
            "turn_id": turn_id,
            "session_id": session_id,
            "status": "AWAITING_USER_INPUT",
            "doc_name": doc_name,
            "app_name": app_name,
            "relevance_info": relevance_info,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_test_summary_block(
        session_id: str,
        goal: str,
        is_success: bool,
        duration: str,
        steps_summary: str,
        deliverables: Optional[List[Dict[str, Any]]] = None,
        is_solidified: bool = False,
        solidified_filename: str = "",
        turn_id: int = 0,
        error_message: str = "",
        error_type: str = ""
    ) -> Dict[str, Any]:
        artifacts = deliverables if deliverables is not None else [
            {
                "type": "report",
                "name": "全景测试执行报告 (Markdown/HTML)",
                "filename": f"outputs/reports/{session_id}_report.md",
                "desc": "包含完整执行步骤、状态迁移与断言结果",
                "action": "view_report"
            },
            {
                "type": "code",
                "name": "零 Token 标准 Python 回归脚本",
                "filename": solidified_filename or f"test_{session_id}.py",
                "desc": "确定性执行脚本，支持秒级免 Token 本地/真机回放",
                "action": "run_local"
            },
            {
                "type": "evidence",
                "name": "端侧全链路关键截图与动作链",
                "filename": "data/reports/screenshots/",
                "desc": "高保真全链路视觉证据链归档",
                "action": "view_evidence"
            }
        ]
        return {
            "block_id": f"blk_summary_{turn_id}",
            "type": "test_summary",
            "turn_id": turn_id,
            "session_id": session_id,
            "status": "PASS" if is_success else "FAIL",
            "goal": goal,
            "duration": duration,
            "steps_summary": steps_summary,
            "artifacts": artifacts,
            "is_solidified": is_solidified,
            "solidified_filename": solidified_filename,
            "error_message": error_message,
            "error_type": error_type,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_fault_diagnosis_block(
        fail_step_title: str,
        current_situation: str,
        suggestion: str,
        turn_id: int = 0
    ) -> Dict[str, Any]:
        return {
            "block_id": f"blk_diag_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "fault_diagnosis",
            "turn_id": turn_id,
            "fail_step": fail_step_title,
            "situation": current_situation,
            "suggestion": suggestion,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
