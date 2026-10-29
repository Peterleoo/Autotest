import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

class TimelineManager:
    """
    负责维护与组装移动端 AI 测试的主流 Stream Timeline Block 事件模型
    严格对齐 Cursor / Claude Artifacts 工业标准事件流
    """

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
        turn_id: int = 0,
        summary_text: str = ""
    ) -> Dict[str, Any]:
        """
        生成任务清单卡片，支持与上一轮任务进行对比 Diff：
        清晰标注新增、进行中、已完成、移除
        """
        completed_count = sum(1 for s in steps if s.get("status") in ["COMPLETED", "PASS"])
        total_count = len(steps)

        # 计算增量对比 Diff
        added_count = 0
        removed_count = 0
        diff_items = []

        if previous_steps:
            prev_titles = set(s.get("title", "") for s in previous_steps)
            curr_titles = set(s.get("title", "") for s in steps)
            
            for s in steps:
                t = s.get("title", "")
                st = s.get("status", "PENDING")
                is_new = t not in prev_titles
                if is_new:
                    added_count += 1
                diff_items.append({
                    "title": t,
                    "desc": s.get("desc", ""),
                    "status": st,
                    "diff_type": "added" if is_new else ("completed" if st == "COMPLETED" else "normal")
                })

            for ps in previous_steps:
                if ps.get("title", "") not in curr_titles:
                    removed_count += 1
                    diff_items.append({
                        "title": ps.get("title", ""),
                        "desc": ps.get("desc", ""),
                        "status": "REMOVED",
                        "diff_type": "removed"
                    })
        else:
            added_count = total_count
            for s in steps:
                diff_items.append({
                    "title": s.get("title", ""),
                    "desc": s.get("desc", ""),
                    "status": s.get("status", "PENDING"),
                    "diff_type": "added"
                })

        title_str = summary_text or f"更新任务清单 · {completed_count}/{total_count} 已完成"
        if added_count > 0 or removed_count > 0:
            title_str += f" · 新增 {added_count} · 移除 {removed_count}"

        return {
            "block_id": f"blk_todo_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "todo_list",
            "turn_id": turn_id,
            "status": "COMPLETED" if (completed_count == total_count and total_count > 0) else "RUNNING",
            "title": title_str,
            "completed_count": completed_count,
            "total_count": total_count,
            "items": diff_items,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_tool_call_block(
        tool_name: str,
        title: str,
        detail: str,
        status: str = "COMPLETED",
        turn_id: int = 0
    ) -> Dict[str, Any]:
        """
        生成工具调用微胶囊（点击/滑动/OCR/断言等）
        """
        icon_map = {
            "ocr": "bi-eye",
            "tap": "bi-hand-index-thumb",
            "swipe": "bi-arrows-vertical",
            "input": "bi-keyboard",
            "assert": "bi-check2-circle",
            "file": "bi-file-earmark-code"
        }
        icon = icon_map.get(tool_name, "bi-cpu")
        return {
            "block_id": f"blk_tool_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "tool_call",
            "turn_id": turn_id,
            "tool_name": tool_name,
            "icon": icon,
            "title": title,
            "detail": detail,
            "status": status,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_step_result_block(
        step_id: int,
        title: str,
        detail: str,
        is_success: bool = True,
        turn_id: int = 0
    ) -> Dict[str, Any]:
        return {
            "block_id": f"blk_stepres_{turn_id}_{step_id}_{uuid.uuid4().hex[:6]}",
            "type": "step_result",
            "turn_id": turn_id,
            "step_id": step_id,
            "title": f"Step {step_id}: {title} {'验证通过 ✅' if is_success else '验证受阻 ❌'}",
            "detail": detail,
            "status": "PASS" if is_success else "FAIL",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_step_execution_block(
        step_id: int,
        title: str,
        actions: List[Dict[str, Any]],
        assertion_result: str = "",
        status: str = "COMPLETED",
        duration: str = "0.4s",
        turn_id: int = 0,
        thinking: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        动作执行容器卡片 (Execution Container)
        按阶段将思考推演、原子动作与断言结果聚合为一个优雅的收放容器卡片
        """
        import re
        clean_title = re.sub(r"^Step\s*\d+\s*[:：]\s*", "", title, flags=re.I).strip()
        return {
            "block_id": f"blk_step_exec_{turn_id}_{step_id}",
            "type": "step_execution",
            "turn_id": turn_id,
            "step_id": step_id,
            "title": clean_title,
            "status": status,
            "duration": duration,
            "thinking": thinking or {},
            "actions": actions,
            "assertion_result": assertion_result,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_report_block(markdown_content: str, session_id: str, turn_id: int = 0) -> Dict[str, Any]:
        return {
            "block_id": f"blk_report_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "final_report",
            "turn_id": turn_id,
            "session_id": session_id,
            "status": "COMPLETED",
            "content": markdown_content,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_test_summary_block(
        session_id: str,
        goal: str = "",
        is_success: bool = True,
        duration: str = "5.14s",
        steps_summary: str = "全链路步骤已验证通过",
        deliverables: Optional[List[Dict[str, Any]]] = None,
        is_solidified: bool = False,
        solidified_filename: str = "",
        turn_id: int = 0,
        error_message: str = "",
        error_type: str = ""
    ) -> Dict[str, Any]:
        """
        生成测试结果全景总结卡片：
        包含测试结论、核心指标总结、结构化交付资产清单（报告、Python脚本、截图证据链、接口）以及保存本地用例操作
        """
        if not is_success:
            artifacts = []
        else:
            artifacts = deliverables or [
                {
                    "type": "report",
                    "name": "6大维度全景交付物报告",
                    "filename": f"test_report_{session_id}.md",
                    "desc": "包含功能闭环、UI感知、断言判定与性能稳定性全景分析",
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
        """
        生成三段式通俗人话自测受阻诊断卡片：
        ① 发生何事 ② 现场现状 ③ 处置建议
        """
        return {
            "block_id": f"blk_diag_{turn_id}_{uuid.uuid4().hex[:6]}",
            "type": "fault_diagnosis",
            "turn_id": turn_id,
            "fail_step": fail_step_title,
            "situation": current_situation,
            "suggestion": suggestion,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
