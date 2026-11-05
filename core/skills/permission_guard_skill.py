# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
from core.skills.base_skill import BaseTestSkill


class PermissionGuardSkill(BaseTestSkill):
    """
    系统权限与协议阻断放行技能 (Permission Guard Skill)
    场景：Android 系统弹出的存储、定位、通知等运行时权限对话框，或应用首次启动时的隐私协议确认
    """
    @property
    def skill_id(self) -> str:
        return "permission_guard"

    @property
    def name(self) -> str:
        return "系统权限与协议弹窗智能放行"

    @property
    def description(self) -> str:
        return "自动识别系统运行时权限弹窗、通知/定位申请与隐私协议，秒级快捷允许放行"

    def should_activate(self, screen_info: Dict[str, Any], goal: str = "") -> bool:
        elements = screen_info.get("elements", [])
        keywords = ["允许", "始终允许", "仅在使用中允许", "同意并继续", "同意", "开启权限", "我知道了", "授权"]
        for el in elements:
            t = (el.get("text") or el.get("desc") or "").strip()
            if any(k == t for k in keywords):
                return True
        return False

    def quick_action(self, screen_info: Dict[str, Any], goal: str = "") -> Optional[Dict[str, Any]]:
        # 寻找最高置信度的允许按钮执行快捷点击
        elements = screen_info.get("elements", [])
        priority_keywords = ["允许", "仅在使用中允许", "始终允许", "同意并继续", "同意", "我知道了"]
        for kw in priority_keywords:
            for el in elements:
                t = (el.get("text") or el.get("desc") or "").strip()
                if t == kw:
                    ref_tag = el.get("ref")
                    idx = el.get("index")
                    return {
                        "action": "tap",
                        "ref": ref_tag,
                        "target_index": idx,
                        "reason": f"【技能触发·权限放行】识别到前台权限/协议弹窗，快捷点击「{kw}」放行进入主流程"
                    }
        return None

    def get_prompt_patch(self, screen_info: Dict[str, Any], goal: str = "") -> str:
        return "【技能指南·权限协议放行】：当前界面存在系统权限申请或协议弹窗，属于前置阻断节点，请优先点击‘允许’或‘同意’。"
