# -*- coding: utf-8 -*-
import re
from typing import Dict, Any, Optional
from core.skills.base_skill import BaseTestSkill


class SmsCodeSkill(BaseTestSkill):
    """
    短信验证码鉴权场景技能 (SMS Code Skill)
    场景：手机号快捷登录、验证码校验等双阶段业务场景
    """
    @property
    def skill_id(self) -> str:
        return "sms_code"

    @property
    def name(self) -> str:
        return "短信验证码鉴权专项技能"

    @property
    def description(self) -> str:
        return "精准区分验证码获取阶段与已发码阶段，指导系统自动代填或适时唤起人机协同"

    def should_activate(self, screen_info: Dict[str, Any], goal: str = "") -> bool:
        elements = screen_info.get("elements", [])
        keywords = ["验证码", "获取验证码", "重新发送", "重发", "短信", "输入验证码"]
        for el in elements:
            t = (el.get("text") or el.get("desc") or "").strip()
            if any(k in t for k in keywords):
                return True
        return False

    def get_prompt_patch(self, screen_info: Dict[str, Any], goal: str = "") -> str:
        # 判断当前是阶段一（未发码）还是阶段二（已发码）
        elements = screen_info.get("elements", [])
        has_countdown = False
        for el in elements:
            t = (el.get("text") or el.get("desc") or "").strip()
            if re.search(r"\d+s|倒计时|已发送|秒后重发", t):
                has_countdown = True
                break

        if has_countdown:
            return (
                "【技能指南·短信验证码(阶段二: 已发码)】：当前页面已进入倒计时，真机已下发短信验证码。"
                "因验证码在物理 SIM 卡中，严禁凭空臆造虚假数字！请果断调用 request_human_help 动作请求人类协助填入。"
            )
        else:
            return (
                "【技能指南·短信验证码(阶段一: 未获取)】：当前页面尚未发送验证码。"
                "请先输入手机号并勾选服务协议，然后点击「获取验证码」，严禁直接索要短信验证码！"
            )
