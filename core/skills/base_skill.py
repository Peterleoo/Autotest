# -*- coding: utf-8 -*-
"""
业务测试技能基础协议 (Base Test Skill Protocol)
借鉴 Vercel Labs vercel-labs/skills 规范：
定义可复用的专项业务领域技能，支持按需激活、动态 Prompt 补丁与快捷自愈动作。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseTestSkill(ABC):
    @property
    @abstractmethod
    def skill_id(self) -> str:
        """技能唯一英文标识"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """技能中文名称"""
        pass

    @property
    def description(self) -> str:
        """技能适用场景描述"""
        return ""

    @abstractmethod
    def should_activate(self, screen_info: Dict[str, Any], goal: str = "") -> bool:
        """判断当前界面特征是否命中了该专项技能的触发条件"""
        pass

    def get_prompt_patch(self, screen_info: Dict[str, Any], goal: str = "") -> str:
        """当技能激活时，向大模型按需注入的轻量领域专业指南（Progressive Disclosure）"""
        return ""

    def quick_action(self, screen_info: Dict[str, Any], goal: str = "") -> Optional[Dict[str, Any]]:
        """
        可选的确定性快捷动作（Short-circuit Action）：
        若该技能具备 100% 确定性处置方案（如直接点击系统权限允许按钮），可直接返回动作字典，
        跳过大模型调用，实现 0 Token 开销与毫秒级极速自愈。
        """
        return None
