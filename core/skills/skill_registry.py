# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, List, Optional, Tuple
from core.skills.base_skill import BaseTestSkill
from core.skills.permission_guard_skill import PermissionGuardSkill
from core.skills.sms_code_skill import SmsCodeSkill
from core.skills.slider_captcha_skill import SliderCaptchaSkill

logger = logging.getLogger("SkillRegistry")


class SkillRegistry:
    """
    业务测试技能中心 (Test Skills Registry)
    借鉴 Vercel Labs vercel-labs/skills 规范：
    1. 集中管理与索引所有可用的端侧测试专项技能；
    2. 基于当前真机屏幕感知特征，按需动态评估与激活（Progressive Skill Activation）；
    3. 支持快捷自愈动作分流与动态 Prompt 微补丁装配。
    """
    _skills: List[BaseTestSkill] = [
        PermissionGuardSkill(),
        SmsCodeSkill(),
        SliderCaptchaSkill(),
    ]

    @classmethod
    def register_skill(cls, skill: BaseTestSkill):
        """支持第三方或用户自定义扩展新技能"""
        if not any(s.skill_id == skill.skill_id for s in cls._skills):
            cls._skills.append(skill)
            logger.info(f"✨ [SkillRegistry] 成功注册扩展技能: {skill.name} ({skill.skill_id})")

    @classmethod
    def list_skills(cls) -> List[Dict[str, str]]:
        return [
            {
                "skill_id": s.skill_id,
                "name": s.name,
                "description": s.description
            }
            for s in cls._skills
        ]

    @classmethod
    def evaluate_and_activate(
        cls,
        screen_info: Dict[str, Any],
        goal: str = ""
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        核心方法：评估当前界面特征并按需激活相关技能
        返回：
        - quick_action: 若命中确定性快捷动作则返回，可零成本秒级放行；
        - prompt_patch: 所有激活技能的领域专业微补丁聚合文本。
        """
        activated_skills: List[BaseTestSkill] = []
        for s in cls._skills:
            try:
                if s.should_activate(screen_info, goal):
                    activated_skills.append(s)
            except Exception as e:
                logger.warning(f"技能 {s.skill_id} 条件评估异常: {e}")

        if not activated_skills:
            return None, ""

        logger.info(f"🎯 [SkillRegistry] 动态激活 {len(activated_skills)} 项业务技能: {[s.name for s in activated_skills]}")

        # 1. 检查是否存在快捷确定性动作 (例如点击权限允许)
        for s in activated_skills:
            try:
                act = s.quick_action(screen_info, goal)
                if act:
                    logger.info(f"⚡ [SkillRegistry] 技能 [{s.name}] 输出快捷短路动作，零 Token 极速自愈")
                    return act, ""
            except Exception as e:
                logger.warning(f"技能 {s.skill_id} 快捷动作生成异常: {e}")

        # 2. 聚合激活技能的 Prompt 指南补丁
        patches = []
        for s in activated_skills:
            try:
                patch = s.get_prompt_patch(screen_info, goal)
                if patch:
                    patches.append(patch)
            except Exception as e:
                logger.warning(f"技能 {s.skill_id} 获取指南异常: {e}")

        combined_patch = "\n".join(patches)
        return None, combined_patch
