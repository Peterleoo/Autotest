# -*- coding: utf-8 -*-
import unittest
from core.skills.skill_registry import SkillRegistry
from core.skills.permission_guard_skill import PermissionGuardSkill
from core.skills.sms_code_skill import SmsCodeSkill
from core.skills.slider_captcha_skill import SliderCaptchaSkill


class TestSkillsRegistry(unittest.TestCase):
    def test_permission_guard_skill_quick_action(self):
        """测试权限弹窗技能命中时直接输出快捷放行动作，实现 0 Token 毫秒级自愈"""
        screen_info = {
            "elements": [
                {"index": 1, "ref": "@e1", "text": "是否允许应用访问此设备的存储空间？", "clickable": False},
                {"index": 2, "ref": "@e2", "text": "拒绝", "clickable": True},
                {"index": 3, "ref": "@e3", "text": "允许", "clickable": True}
            ]
        }
        quick_act, patch = SkillRegistry.evaluate_and_activate(screen_info)
        self.assertIsNotNone(quick_act, "权限弹窗场景应输出 quick_action")
        self.assertEqual(quick_act["action"], "tap")
        self.assertEqual(quick_act["ref"], "@e3")
        self.assertIn("权限放行", quick_act["reason"])

    def test_sms_code_skill_stage_one_and_stage_two(self):
        """测试短信验证码技能在阶段一（未发码）和阶段二（已发码倒计时）的分阶段精准指南"""
        # 阶段一：未发码，包含“获取验证码”
        screen_stage1 = {
            "elements": [
                {"index": 1, "ref": "@e1", "text": "手机快捷登录", "clickable": False},
                {"index": 2, "ref": "@e2", "desc": "请输入手机号", "clickable": True},
                {"index": 3, "ref": "@e3", "text": "获取验证码", "clickable": True}
            ]
        }
        quick_act1, patch1 = SkillRegistry.evaluate_and_activate(screen_stage1)
        self.assertIsNone(quick_act1)
        self.assertIn("阶段一: 未获取", patch1)
        self.assertIn("先输入手机号", patch1)

        # 阶段二：已发码，包含倒计时“58s后重发”
        screen_stage2 = {
            "elements": [
                {"index": 1, "ref": "@e1", "text": "请输入短信验证码", "clickable": False},
                {"index": 2, "ref": "@e2", "desc": "验证码输入框", "clickable": True},
                {"index": 3, "ref": "@e3", "text": "58s后重新获取", "clickable": False}
            ]
        }
        quick_act2, patch2 = SkillRegistry.evaluate_and_activate(screen_stage2)
        self.assertIsNone(quick_act2)
        self.assertIn("阶段二: 已发码", patch2)
        self.assertIn("request_human_help", patch2)

    def test_slider_captcha_skill(self):
        """测试滑动拼图技能命中与指南注入"""
        screen_slider = {
            "elements": [
                {"index": 1, "ref": "@e1", "text": "安全验证", "clickable": False},
                {"index": 2, "ref": "@e2", "text": "向右滑动完成拼图", "clickable": False},
                {"index": 3, "ref": "@e3", "desc": "滑块按钮", "clickable": True}
            ]
        }
        quick_act, patch = SkillRegistry.evaluate_and_activate(screen_slider)
        self.assertIsNone(quick_act)
        self.assertIn("滑动拼图防刷拦截", patch)
        self.assertIn("水平拖拽滑动动作", patch)


if __name__ == '__main__':
    unittest.main()
