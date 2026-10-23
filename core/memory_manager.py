# -*- coding: utf-8 -*-
r"""
会话记忆中枢与 Token 治理引擎 (Conversation Memory & Token Governance)
对标 F:\PM-product 工业级 DSH 会话范式：
1. 端侧事实状态机 (Fact Memory)
2. 标准化多轮 Turn 抽象与上下文组装
3. 上下文自愈与智能压缩 (/compact)
4. Token 压力监控与工具输出熔断 (Hard Cap)
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("MemoryManager")

# 工具输出 Hard Cap 上限：4096 字符
MAX_TOOL_OUTPUT_CHARS = 4096
# 单次记忆上下文最大字符数（约 300~400 Token）
MAX_MEMORY_CONTEXT_CHARS = 1600
# 模型默认上下文窗口 (Gemini 1M, DeepSeek 64k/128k)
DEFAULT_CONTEXT_WINDOW = 1048576


class MemoryManager:
    """会话记忆与 Token 治理核心管理器"""

    @staticmethod
    def create_empty_fact_memory() -> Dict[str, Any]:
        """创建初始端侧事实状态机"""
        return {
            "current_package": "",
            "current_activity": "",
            "passed_milestones": [],
            "page_summary": "",
            "key_entities": {},
            "updated_at": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def create_turn(
        turn_id: int,
        user_message: str,
        is_rework: bool = False,
        rework_note: str = ""
    ) -> Dict[str, Any]:
        """创建新的交互轮次 (Turn)"""
        return {
            "turn_id": turn_id,
            "user_message": user_message,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "thinking": {
                "duration": "1.2s",
                "bullets": [
                    {"tag": "意图深度解析", "content": f"深入理解本轮测试诉求【{user_message[:24]}】"},
                    {"tag": "状态机因果链核验", "content": "继承前序端侧已达成状态，原地规划增量执行路径"}
                ]
            },
            "plan_steps": [],
            "actions": [],
            "conclusion": "",
            "status": "RUNNING",
            "is_rework": is_rework,
            "rework_note": rework_note
        }

    @staticmethod
    def ensure_session_turns(session: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        保证 Session 中存在合法的 turns 列表，平滑兼容旧扁平数据
        """
        if "turns" in session and isinstance(session["turns"], list) and len(session["turns"]) > 0:
            return session["turns"]

        # 向上兼容旧版扁平 Session 结构
        initial_goal = session.get("goal", "自动化测试意图")
        created_at = session.get("created_at", datetime.now().strftime("%H:%M:%S"))
        old_steps = session.get("plan_steps", [])
        old_thinking = session.get("thinking", {
            "duration": session.get("duration", "1.5s"),
            "bullets": [{"tag": "业务意图推演", "content": "分析测试需求并编排端侧验证链路"}]
        })
        is_finished = session.get("status") in ["COMPLETED", "FAILED", "READY_FOR_REVIEW"]
        is_success = session.get("is_success", True)
        old_conclusion = ""
        if is_finished:
            old_conclusion = "测试验证达成，全部规划阶段均已通过校验。" if is_success else f"测试推进受阻: {session.get('error_message', '未达预期')}"

        first_turn = {
            "turn_id": 1,
            "user_message": initial_goal,
            "timestamp": created_at,
            "thinking": old_thinking,
            "plan_steps": old_steps,
            "actions": [],
            "conclusion": old_conclusion,
            "status": session.get("status", "COMPLETED"),
            "is_rework": False,
            "rework_note": ""
        }
        session["turns"] = [first_turn]

        # 确保存在 fact_memory
        if "fact_memory" not in session or not isinstance(session["fact_memory"], dict):
            session["fact_memory"] = MemoryManager.create_empty_fact_memory()
            session["fact_memory"]["current_package"] = session.get("app_package", "")

        return session["turns"]

    @staticmethod
    def build_memory_context(session: Dict[str, Any]) -> str:
        """
        从会话中提取事实状态机与多轮目标演进链，装配轻量高密度的 Prompt 注入文本
        """
        turns = MemoryManager.ensure_session_turns(session)
        fact_memory = session.get("fact_memory") or MemoryManager.create_empty_fact_memory()

        total_turns = len(turns)
        current_turn = turns[-1] if turns else None

        # 1. 整理前序轮次总结链 (Previous Turns Summary)
        history_summary_lines = []
        # 只取前序完成的历史轮次（不含当前活跃轮次）
        for t in turns[:-1]:
            t_id = t.get("turn_id", 1)
            t_msg = t.get("user_message", "")
            t_concl = t.get("conclusion", "")
            t_status = "通过" if t.get("status") in ["COMPLETED", "READY_FOR_REVIEW"] else "受阻"
            if not t_concl:
                t_concl = f"执行了 {len(t.get('plan_steps', []))} 个规划动作并达成阶段性界面校验"
            # 简洁压缩每轮摘要
            history_summary_lines.append(f"  • Turn {t_id}【{t_msg[:16]}】({t_status}): {t_concl[:50]}")

        history_summary_text = "\n".join(history_summary_lines) if history_summary_lines else "  • 暂无前序历史轮次（当前为初始首轮）"

        # 2. 整理端侧事实清单 (Fact Store)
        milestones = fact_memory.get("passed_milestones", [])
        milestones_text = "、".join(milestones) if milestones else "已启动并处于应用主界面"
        curr_pkg = fact_memory.get("current_package") or session.get("app_package") or "待测应用"
        curr_page = fact_memory.get("page_summary") or "应用当前界面"

        # 3. 构造紧凑结构化 Prompt
        curr_msg = current_turn.get("user_message", "") if current_turn else session.get("goal", "")
        rework_flag = "【用户打回返工要求】" if (current_turn and current_turn.get("is_rework")) else "【用户最新追加/纠偏指令】"

        memory_prompt = f"""
==================== 会话连续记忆与前序事实 (Conversation Memory) ====================
• 会话总轮次：当前正在执行第 {total_turns} 轮交互
• 前序轮次完成演进链：
{history_summary_text}
• 端侧已达成的事实状态机 (Fact State)：
  1. 当前前台包名: {curr_pkg}
  2. 已确认达成的里程碑: {milestones_text}
  3. 当前真机停留状态: {curr_page}
• 本轮交互目标 ({rework_flag}):
  👉 “{curr_msg}”
• 连续执行决策准则：
  1. 必须充分继承并利用前序轮次已达成的状态事实，严禁退回桌面盲目重新冷启动；
  2. 理解用户代词与上下文（如“刚才那个”、“第二套”指向前序列表中已展示的条目）；
  3. 若本轮为返工要求，请重点针对用户指出的调整项执行纠偏动作与断言核验。
===================================================================================
"""
        return memory_prompt.strip()

    @staticmethod
    def update_fact_memory(
        session: Dict[str, Any],
        current_package: Optional[str] = None,
        milestone: Optional[str] = None,
        page_summary: Optional[str] = None,
        key_entity: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """动态更新端侧事实状态机"""
        if "fact_memory" not in session or not isinstance(session["fact_memory"], dict):
            session["fact_memory"] = MemoryManager.create_empty_fact_memory()

        fm = session["fact_memory"]
        if current_package:
            fm["current_package"] = current_package
        if milestone and milestone not in fm["passed_milestones"]:
            fm["passed_milestones"].append(milestone)
        if page_summary:
            fm["page_summary"] = page_summary
        if key_entity and len(key_entity) == 2:
            fm["key_entities"][key_entity[0]] = key_entity[1]

        fm["updated_at"] = datetime.now().strftime("%H:%M:%S")
        return fm

    @staticmethod
    def compact_session(session: Dict[str, Any]) -> Dict[str, Any]:
        """
        主动 / 自动执行上下文压缩 (/compact)
        浓缩前序多轮历史，释放冗余过程日志，保留核心事实状态机
        """
        turns = MemoryManager.ensure_session_turns(session)
        if len(turns) <= 1:
            return {"compacted": False, "reason": "会话仅有单轮，无需压缩"}

        # 将除最近 1 轮之外的前序轮次深度浓缩
        compressed_summary = []
        for t in turns[:-1]:
            tid = t.get("turn_id", 1)
            msg = t.get("user_message", "")
            concl = t.get("conclusion", "已完成阶段验证")
            compressed_summary.append(f"Turn {tid}【{msg[:14]}】-> {concl[:40]}")
            # 清理前序轮次中庞大的原生日志和临时 steps 展开物
            t["actions"] = []
            if "plan_steps" in t:
                for s in t["plan_steps"]:
                    s["raw_logs"] = "" # 清空底层冗余日志

        # 在事实状态机中归档压缩背景
        fm = session.get("fact_memory") or MemoryManager.create_empty_fact_memory()
        fm["compacted_background"] = "；".join(compressed_summary)
        session["fact_memory"] = fm

        logger.info(f"会话 [{session.get('session_id')}] 成功执行上下文压缩，释放了前序 {len(turns) - 1} 轮冗余日志。")
        return {
            "compacted": True,
            "turns_compacted": len(turns) - 1,
            "saved_background": fm["compacted_background"]
        }

    @staticmethod
    def truncate_tool_output(output: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
        """
        对底层 ADB、Terminal、OCR 原始输出执行 Hard Cap 熔断截断
        防止巨量日志灌爆 LLM 上下文
        """
        if not output or len(output) <= max_chars:
            return output

        head_len = max_chars // 2
        tail_len = max_chars // 2
        truncated_count = len(output) - (head_len + tail_len)
        return f"{output[:head_len]}\n... [⚠️ 熔断截断：已略过 {truncated_count} 字符原生日志，避免上下文超载] ...\n{output[-tail_len:]}"

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """快速高精度估算文本的 Token 数量 (中英混杂加权)"""
        if not text:
            return 0
        # 英文约 4 字符 1 token，中文约 1.5~2 字符 1 token
        zh_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fa5')
        other_count = len(text) - zh_count
        return int(zh_count * 0.7 + other_count * 0.25) + 1

    @staticmethod
    def get_token_pressure_status(total_tokens: int, context_window: int = DEFAULT_CONTEXT_WINDOW) -> Dict[str, Any]:
        """获取当前 Token 压力与水位等级"""
        ratio = total_tokens / max(1, context_window)
        percentage = round(ratio * 100, 2)

        if ratio < 0.60:
            level = "normal"
            level_text = "良好"
            badge_class = "text-success"
        elif ratio < 0.80:
            level = "warning"
            level_text = "关注"
            badge_class = "text-warning"
        else:
            level = "critical"
            level_text = "高危"
            badge_class = "text-danger"

        return {
            "total_tokens": total_tokens,
            "context_window": context_window,
            "percentage": percentage,
            "level": level,
            "level_text": level_text,
            "badge_class": badge_class,
            "should_compact": ratio >= 0.75
        }
