# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
from core.skills.base_skill import BaseTestSkill


class SliderCaptchaSkill(BaseTestSkill):
    """
    图形滑动验证码与滑块拼图技能 (Slider Captcha Skill)
    场景：极验、网易易盾、腾讯天御等图形滑块拼图防刷防刷拦截
    """
    @property
    def skill_id(self) -> str:
        return "slider_captcha"

    @property
    def name(self) -> str:
        return "滑动拼图验证码感知技能"

    @property
    def description(self) -> str:
        return "智能识别图形滑动拼图并给出向右拖动手势决策或唤起人机协助"

    def should_activate(self, screen_info: Dict[str, Any], goal: str = "") -> bool:
        elements = screen_info.get("elements", [])
        keywords = ["向右滑动", "拖动滑块", "完成拼图", "拖动到最右", "滑块验证", "按住滑块"]
        for el in elements:
            t = (el.get("text") or el.get("desc") or "").strip()
            if any(k in t for k in keywords):
                return True
        return False

    def get_prompt_patch(self, screen_info: Dict[str, Any], goal: str = "") -> str:
        return (
            "【技能指南·滑动拼图防刷拦截】：当前检测到图形滑动拼图或防刷滑块验证。"
            "可尝试定位滑块控件执行从左向右的水平拖拽滑动动作，或在反复失败时调用 request_human_help 唤起投屏手动协助。"
        )
