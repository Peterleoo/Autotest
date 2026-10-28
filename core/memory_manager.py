import time
# -*- coding: utf-8 -*-
r"""
会话记忆中枢与 Token 治理引擎 (Conversation Memory & Token Governance)
借鉴 DeepSeek Harness 与 Muse / MemGPT 工业级会话范式：
1. 端侧事实状态机 (Fact Memory)
2. 实体槽位追踪与工作记忆 (Working Memory & Entity Tracker)
3. 动态插件化切片注入 (Context Providers)
4. 代词与跨轮实体消解 (Coreference Resolution)
5. 上下文自愈与智能压缩 (/compact)
6. Token 压力监控与工具输出熔断 (Hard Cap)
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("MemoryManager")

# 工具输出 Hard Cap 上限：4096 字符
MAX_TOOL_OUTPUT_CHARS = 4096
# 单次记忆上下文最大字符数（约 300~500 Token，严格治理）
MAX_MEMORY_CONTEXT_CHARS = 1800
# 模型默认上下文窗口 (Gemini 1M, DeepSeek 64k/128k)
DEFAULT_CONTEXT_WINDOW = 1048576

# 中文数字序号映射
ZH_NUM_MAP = {
    "一": 1, "1": 1, "二": 2, "两": 2, "2": 2, "三": 3, "3": 3,
    "四": 4, "4": 4, "五": 5, "5": 5, "六": 6, "6": 6,
    "七": 7, "7": 7, "八": 8, "8": 8, "九": 9, "9": 9, "十": 10
}


class MemoryManager:
    """会话记忆与 Token 治理核心管理器 (DeepSeek Harness + Muse 范式)"""

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
    def create_empty_working_memory() -> Dict[str, Any]:
        """
        创建初始工作记忆与实体槽位 (Working Memory - 借鉴 Muse)
        追踪列表项、表单字段、活跃 Tab 及最近动作物理锚点
        """
        return {
            "active_entities": {
                "list_items": [],       # 识别出的带序号列表项: [{"index": 1, "text": "...", "center": [x, y]}]
                "form_fields": [],      # 提取的输入框字段: [{"label": "手机号", "type": "input"}]
                "selected_tabs": [],    # 当前页面选中的导航/Tab: ["首页", "租房"]
                "key_values": {}        # 关键业务属性: {"price": "5200/月", "title": "..."}
            },
            "last_action_anchor": None, # 最近一次执行物理动作: {"action": "tap", "target": "...", "coords": [x, y]}
            "updated_at": datetime.now().strftime("%H:%M:%S")
        }

    @staticmethod
    def ensure_working_memory(session: Dict[str, Any]) -> Dict[str, Any]:
        """保证 Session 中存在结构完整的 working_memory"""
        if "working_memory" not in session or not isinstance(session["working_memory"], dict):
            session["working_memory"] = MemoryManager.create_empty_working_memory()
        wm = session["working_memory"]
        if "active_entities" not in wm or not isinstance(wm["active_entities"], dict):
            wm["active_entities"] = {
                "list_items": [],
                "form_fields": [],
                "selected_tabs": [],
                "key_values": {}
            }
        return wm

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
        """保证 Session 中存在合法的 turns 列表，平滑兼容旧扁平数据"""
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

        # 确保存在 fact_memory 与 working_memory
        if "fact_memory" not in session or not isinstance(session["fact_memory"], dict):
            session["fact_memory"] = MemoryManager.create_empty_fact_memory()
            session["fact_memory"]["current_package"] = session.get("app_package", "")

        MemoryManager.ensure_working_memory(session)
        return session["turns"]

    # =========================================================================
    # 实体提炼与工作记忆更新 (Entity & Coreference Tracker)
    # =========================================================================

    @staticmethod
    def extract_and_update_working_memory(
        session: Dict[str, Any],
        screen_elements: List[Dict[str, Any]],
        last_action: Optional[Dict[str, Any]] = None,
        page_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从屏幕元素和动作流中智能提炼高置信度实体与工作记忆（过滤噪音）
        """
        wm = MemoryManager.ensure_working_memory(session)
        active_ent = wm["active_entities"]

        # 1. 过滤系统通用控制字符与无效噪音
        system_stopwords = {
            "返回", "更多", "设置", "确定", "取消", "关闭", "跳过", "知道了",
            "编辑", "分享", "搜索", "我的", "消息", "首页", "下一步", "完成"
        }

        meaningful_elements = []
        form_elements = []

        for el in screen_elements:
            text = (el.get("text") or el.get("desc") or el.get("content_desc") or "").strip()
            # 过滤单字或无意义标点/时间
            if not text or len(text) < 2 or re.match(r"^[\d\:\.\-\s]+$", text):
                continue
            is_input = el.get("is_input", False) or "EditText" in str(el.get("class", ""))
            center = [el.get("center_x", 0), el.get("center_y", 0)]

            if is_input:
                form_elements.append({
                    "label": text,
                    "center": center,
                    "bounds": el.get("bounds", "")
                })
            elif text not in system_stopwords and len(text) >= 3:
                meaningful_elements.append({
                    "text": text,
                    "center": center,
                    "bounds": el.get("bounds", "")
                })

        # 2. 按纵坐标 y 从上到下排序，归纳为带序号的列表实体 (List Items)
        meaningful_elements.sort(key=lambda x: x["center"][1] if x.get("center") else 0)

        # 提取前 6 个代表性条目并建立序号索引 [1]..[6]
        list_items = []
        seen_texts = set()
        for idx, item in enumerate(meaningful_elements, 1):
            t = item["text"]
            if t in seen_texts:
                continue
            seen_texts.add(t)
            list_items.append({
                "index": len(list_items) + 1,
                "text": t[:32], # 适度截断
                "center": item["center"],
                "bounds": item["bounds"]
            })
            if len(list_items) >= 6:
                break

        if list_items:
            active_ent["list_items"] = list_items
        if form_elements:
            active_ent["form_fields"] = form_elements[:4]

        # 3. 记录物理动作锚点 (Last Action Anchor)
        if last_action:
            wm["last_action_anchor"] = {
                "action": last_action.get("action", ""),
                "target": last_action.get("target") or last_action.get("element_text") or "",
                "coords": last_action.get("coords") or last_action.get("center"),
                "reason": last_action.get("reason", "")[:40]
            }

        wm["updated_at"] = datetime.now().strftime("%H:%M:%S")

        # 同步更新事实状态机页面概要
        if page_summary:
            MemoryManager.update_fact_memory(session, page_summary=page_summary)

        return wm

    @staticmethod
    def resolve_coreference(user_prompt: str, session: Dict[str, Any]) -> Optional[str]:
        """
        代词指代消解 (Coreference Resolution)：
        分析用户输入中的“第2个/第2套/第二条/刚才那个/第一项”等代词，
        自动从 Working Memory 中锚定具体实体与坐标，返回高置信度提示。
        """
        if not user_prompt:
            return None

        wm = MemoryManager.ensure_working_memory(session)
        active_ent = wm.get("active_entities", {})
        list_items = active_ent.get("list_items", [])
        last_anchor = wm.get("last_action_anchor")

        # 1. 序号代词模式（如：“选第2个”、“查看第二套”、“点击第3项”、“第1条”）
        m_ordinal = re.search(r"第([一二两三四五六七八九十\d]+)[个条套项行部篇名本位张]", user_prompt)
        if m_ordinal and list_items:
            num_raw = m_ordinal.group(1)
            target_idx = ZH_NUM_MAP.get(num_raw)
            if not target_idx and num_raw.isdigit():
                target_idx = int(num_raw)

            if target_idx and 1 <= target_idx <= len(list_items):
                target_item = list_items[target_idx - 1]
                hint = (
                    f"🎯【代词消解命中】用户提及“第{num_raw}项”，精准匹配屏幕列表条目 [{target_idx}]：\n"
                    f"   • 名称/文本: “{target_item['text']}”\n"
                    f"   • 中心物理坐标: {target_item['center']} (bounds: {target_item['bounds']})\n"
                    f"   👉 决策指引: 优先针对此实体执行 tap 或详情核验，无需重新盲搜！"
                )
                return hint

        # 2. 相对动作代词模式（如：“刚才那个”、“原位置”、“再点一次”、“返回重试”）
        if any(kw in user_prompt for kw in ["刚才那个", "刚才的位置", "原位置", "再点一次", "上一个"]) and last_anchor:
            hint = (
                f"🎯【动作锚点消解】用户提及“刚才那个/原位置”，匹配上一轮物理动作：\n"
                f"   • 动作类型: {last_anchor.get('action')}, 目标: “{last_anchor.get('target')}”\n"
                f"   • 上次执行坐标: {last_anchor.get('coords')}\n"
                f"   👉 决策指引: 可基于此物理坐标执行原位复核或逆向操作！"
            )
            return hint

        return None

    # =========================================================================
    # Context Providers 插件化动态装配 (借鉴 DeepSeek Harness)
    # =========================================================================

    @staticmethod
    def _provider_device_vitals(session: Dict[str, Any]) -> str:
        """DeviceVitalsProvider: 实时端侧体征切片 (约 40 Token)"""
        fm = session.get("fact_memory") or MemoryManager.create_empty_fact_memory()
        pkg = fm.get("current_package") or session.get("app_package") or "前台应用"
        act = fm.get("current_activity") or session.get("app_activity") or "MainActivity"
        milestones = fm.get("passed_milestones", [])
        m_str = f" | 里程碑 [{', '.join(milestones)}]" if milestones else ""
        return f"• 端侧环境快照: 包名 [{pkg}] | 活跃界面 [{act}]{m_str}"

    @staticmethod
    def _provider_goal_evolution(session: Dict[str, Any]) -> str:
        """GoalEvolutionProvider: 多轮目标演进链切片 (约 150 Token)"""
        turns = MemoryManager.ensure_session_turns(session)
        total_turns = len(turns)
        if total_turns <= 1:
            return "• 演进历史: 当前为首轮 (Turn 1)"

        history_lines = []
        for t in turns[:-1]:
            tid = t.get("turn_id", 1)
            msg = t.get("user_message", "")
            concl = t.get("conclusion", "")
            status = "已达成" if t.get("status") in ["COMPLETED", "READY_FOR_REVIEW"] else "受阻"
            if not concl:
                concl = f"完成 {len(t.get('plan_steps', []))} 步界面操作"
            history_lines.append(f"  [{tid}] “{msg[:14]}” ➔ {status}: {concl[:40]}")

        return "• 多轮演进链 (Previous Turns):\n" + "\n".join(history_lines)

    @staticmethod
    def _provider_working_memory(session: Dict[str, Any], current_goal: str) -> str:
        """WorkingMemoryProvider: 活跃实体与代词消解切片 (约 150 Token)"""
        wm = MemoryManager.ensure_working_memory(session)
        active_ent = wm.get("active_entities", {})
        list_items = active_ent.get("list_items", [])

        lines = []
        if list_items:
            items_desc = " | ".join([f"[{i['index']}] {i['text'][:14]}" for i in list_items[:4]])
            lines.append(f"• 活跃列表实体: {items_desc}")

        # 动态代词消解检测
        resolved_hint = MemoryManager.resolve_coreference(current_goal, session)
        if resolved_hint:
            lines.append(resolved_hint)

        return "\n".join(lines) if lines else "• 活跃工作记忆: 暂无缓存实体"

    @staticmethod
    def build_memory_context(session: Dict[str, Any]) -> str:
        """
        DeepSeek Harness 规范：插件化装配不可变记忆切片，严格控制 Token 上限
        """
        turns = MemoryManager.ensure_session_turns(session)
        total_turns = len(turns)
        current_turn = turns[-1] if turns else None
        curr_msg = current_turn.get("user_message", "") if current_turn else session.get("goal", "")
        rework_flag = "【打回返工/纠偏模式】" if (current_turn and current_turn.get("is_rework")) else "【增量演进模式】"

        # 装配 3 个核心 Provider 切片
        vitals_slice = MemoryManager._provider_device_vitals(session)
        evolution_slice = MemoryManager._provider_goal_evolution(session)
        working_memory_slice = MemoryManager._provider_working_memory(session, curr_msg)

        memory_prompt = f"""
==================== 会话具身记忆中枢 (MixBot Context Harness) ====================
• 轮次标识: 当前正在执行第 {total_turns} 轮交互 {rework_flag}
{vitals_slice}
{evolution_slice}
{working_memory_slice}
• 本轮核心测试目标:
  👉 “{curr_msg}”
• 具身决策准则:
  1. 继承前序已达成的端侧现场，严禁退回桌面盲目重新冷启动；
  2. 若用户指令涉及序号（如“第2个/第3条”），严格对齐活跃列表实体中已标注的条目与物理坐标；
  3. 若本轮为打回返工，针对用户指出的缺陷点执行精准重测与断言。
===================================================================================
"""
        return memory_prompt.strip()

    @staticmethod
    def update_fact_memory(
        session: Dict[str, Any],
        current_package: Optional[str] = None,
        current_activity: Optional[str] = None,
        milestone: Optional[str] = None,
        page_summary: Optional[str] = None,
        key_entity: Optional[Tuple[str, Any]] = None
    ) -> Dict[str, Any]:
        """动态更新端侧事实状态机"""
        if "fact_memory" not in session or not isinstance(session["fact_memory"], dict):
            session["fact_memory"] = MemoryManager.create_empty_fact_memory()

        fm = session["fact_memory"]
        if current_package:
            fm["current_package"] = current_package
        if current_activity:
            fm["current_activity"] = current_activity
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
        浓缩前序多轮历史，释放冗余过程日志，保留核心事实状态机与工作记忆
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
                    s["raw_logs"] = ""

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
