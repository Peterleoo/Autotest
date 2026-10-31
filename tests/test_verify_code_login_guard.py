# -*- coding: utf-8 -*-
"""
验证码登录与凭证防混淆注入单元测试
"""

import sys
import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai_engine.verifier import TaskVerifier
from ai_engine.test_agent import AITestAgent
from ai_engine.action_executor import ActionExecutor
from core.task_manager import TaskManager


class TestVerifyCodeLoginGuard(unittest.TestCase):

    def test_01_goal_immunity_for_verify_code_and_robot_check(self):
        """测试 1: 当目标涉及验证码、机器人检测时，享有目标豁免权，不误判为登录屏障"""
        goals = [
            "检测象盒找房的验证码登录页面的机器人检测功能是否正常，是否能绕过",
            "测试短信验证码登录流程",
            "测试登录页面的滑块拼图机器人检测是否能拦截",
            "验证手机验证码登录页面UI组件"
        ]
        for g in goals:
            self.assertTrue(TaskVerifier.is_testing_auth_or_captcha(g), f"目标应具备豁免权: {g}")

        # 非登录验证业务目标应返回 False
        non_auth_goal = "在首页搜索二手房并查看详情"
        self.assertFalse(TaskVerifier.is_testing_auth_or_captcha(non_auth_goal))

    def test_02_check_and_prompt_hitl_skips_when_testing_verify_code(self):
        """测试 2: 测试验证码登录时，_check_and_prompt_hitl_credential 直接放行，不阻断"""
        mock_driver = MagicMock()
        agent = AITestAgent(driver=mock_driver, app_identifier="com.apicloud.A6995433058179")

        mock_screen = {
            "elements": [
                {"text": "手机号登录", "content_desc": "", "bounds": "[0,0][1080,200]"},
                {"text": "用密码登录", "content_desc": "", "bounds": "[90,608][250,650]"},
                {"text": "请输入手机号码", "content_desc": "", "is_input": True, "bounds": "[115,639][965,759]", "center": [540, 699]},
                {"text": "获取验证码", "content_desc": "", "bounds": "[115,800][965,900]"}
            ]
        }
        goal = "检测象盒找房的验证码登录页面的机器人检测功能是否正常，是否能绕过"
        res = agent._check_and_prompt_hitl_credential(mock_screen, goal)
        self.assertFalse(res, "针对验证码登录与机器人检测的目标，门禁必须直接放行给 AI 自主探索！")

    def test_03_credential_injection_does_not_switch_to_pwd_mode_on_verify_intent(self):
        """测试 3: 目标为验证码测试时，凭证注入绝不强切'密码登录'，且绝不把'用密码登录'按钮当成密码输入框"""
        mock_driver = MagicMock()
        mock_driver.execute_adb = MagicMock()
        agent = AITestAgent(driver=mock_driver, app_identifier="com.apicloud.A6995433058179")

        mock_screen = {
            "elements": [
                {"text": "手机号登录", "content_desc": "", "bounds": "[100,200][400,260]"},
                {"text": "用密码登录", "content_desc": "", "bounds": "[90,608][250,650]", "center": [90, 608]},
                {"text": "请输入手机号码", "content_desc": "", "is_input": True, "bounds": "[115,639][965,759]", "center": [540, 699]},
                {"text": "获取验证码", "content_desc": "", "bounds": "[115,800][965,900]", "center": [540, 850]}
            ]
        }

        clicked_texts = []
        typed_entries = []

        def fake_click(el, coords):
            t = (el.get("text") or el.get("content_desc") or "") if el else ""
            clicked_texts.append(t)
            return {"by": "coordinates", "value": "mock"}

        def fake_type(el, text):
            t = (el.get("text") or el.get("content_desc") or "") if el else ""
            typed_entries.append((t, text, el.get("center")))
            return {"by": "coordinates", "value": "mock"}

        agent.executor._locate_and_click = fake_click
        agent.executor._locate_and_type = fake_type

        with patch("ai_engine.screen_parser.ScreenParser.get_screen_summary", return_value={"elements": []}), \
             patch("ai_engine.screen_parser.ScreenParser.wait_for_visual_settling", return_value=True):
            goal = "检测象盒找房的验证码登录页面的机器人检测功能是否正常，是否能绕过"
            agent._execute_credential_injection(acc="18888888888", pwd="xhj123456", screen_info=mock_screen, goal=goal)

        # 1. 验证绝未点击“用密码登录”
        self.assertNotIn("用密码登录", clicked_texts, "验证码意图下严禁点击切换密码登录！")

        # 2. 验证仅向手机号框输入了账号，绝未向任何地方输入密码
        self.assertEqual(len(typed_entries), 1, "只应向手机号框输入账号，绝不能输入密码！")
        target_field, typed_text, center = typed_entries[0]
        self.assertEqual(typed_text, "18888888888")
        self.assertIn("请输入手机号码", target_field)
        self.assertEqual(center, [540, 699])

    def test_04_action_executor_clears_input_before_typing(self):
        """测试 4: 原生 ADB 输入前执行 KEYCODE_MOVE_END 与连续 KEYCODE_DEL 确定性清空"""
        mock_driver = MagicMock()
        mock_driver.execute_adb = MagicMock(return_value=b"")
        executor = ActionExecutor(driver=mock_driver)

        el_info = {
            "text": "请输入手机号码",
            "center": [540, 699]
        }
        executor._locate_and_type(el_info, "13800138000")

        adb_calls = [c[0][0] for c in mock_driver.execute_adb.call_args_list]
        has_move_end = any(cmd == ["shell", "input", "keyevent", "123"] for cmd in adb_calls)
        has_del_sequence = any(cmd[:3] == ["shell", "input", "keyevent"] and "67" in cmd for cmd in adb_calls)
        has_text_input = any(cmd == ["shell", "input", "text", "13800138000"] for cmd in adb_calls)

        self.assertTrue(has_move_end, "必须先发送光标移至末尾事件 (123)")
        self.assertTrue(has_del_sequence, "必须发送批量退格清空事件 (67)")
        self.assertTrue(has_text_input, "必须准确填入目标文本")

    def test_05_detect_login_screen_state_dynamically(self):
        """测试 5: 自适应精准识别端侧真实登录形态 (SMS待填/手机号待获取/滑块拼图/账号密码)"""
        # 场景 A: 短信验证码已发送 (包含重新获取倒计时与验证码输入框)
        screen_sms = {
            "elements": [
                {"text": "验证码已发送至 188****8888"},
                {"text": "请输入验证码", "is_input": True, "bounds": "[100,500][900,600]"},
                {"text": "重新获取(58s)"}
            ]
        }
        state, meta = AITestAgent._detect_login_screen_state(screen_sms)
        self.assertEqual(state, "sms_code", "必须识别为短信验证码待填阶段！")

        # 场景 B: 手机号验证码模式（尚未获取验证码）
        screen_phone = {
            "elements": [
                {"text": "手机号快捷登录"},
                {"text": "请输入手机号码", "is_input": True},
                {"text": "获取验证码"}
            ]
        }
        state, meta = AITestAgent._detect_login_screen_state(screen_phone)
        self.assertEqual(state, "phone_wait_code", "必须识别为手机号待获取验证码阶段！")

        # 场景 C: 图形滑块拼图/机器人检测
        screen_slider = {
            "elements": [
                {"text": "安全验证"},
                {"text": "请按住滑块，拖动完成拼图"}
            ]
        }
        state, meta = AITestAgent._detect_login_screen_state(screen_slider)
        self.assertEqual(state, "manual_takeover", "必须识别为投屏手动接管滑块拼图！")

        # 场景 D: 传统账号密码
        screen_pwd = {
            "elements": [
                {"text": "账号密码登录"},
                {"text": "请输入账号", "is_input": True},
                {"text": "请输入密码", "is_input": True}
            ]
        }
        state, meta = AITestAgent._detect_login_screen_state(screen_pwd)
        self.assertEqual(state, "credential", "必须识别为账号密码模式！")

    def test_06_execute_phone_send_sms_flow(self):
        """测试 6: 手机号阶段自动填入手机号、勾选协议并点击【获取验证码】"""
        mock_driver = MagicMock()
        agent = AITestAgent(driver=mock_driver, app_identifier="demo_app")

        screen_info = {
            "elements": [
                {"text": "请输入手机号码", "is_input": True, "center": [540, 600]},
                {"text": "我已阅读并同意服务协议", "center": [100, 800]},
                {"text": "获取验证码", "center": [540, 700]}
            ]
        }

        clicked = []
        typed = []
        agent.executor._locate_and_click = lambda el, c: clicked.append(el.get("text"))
        agent.executor._locate_and_type = lambda el, t: typed.append((el.get("text"), t))

        res = agent._execute_phone_send_sms("13912345678", screen_info)
        self.assertTrue(res)
        self.assertIn("我已阅读并同意服务协议", clicked)
        self.assertIn("获取验证码", clicked)
        self.assertEqual(typed, [("请输入手机号码", "13912345678")])

    def test_07_execute_sms_code_injection_flow(self):
        """测试 7: 短信验证码阶段精准定位验证码输入框，填入验证码并提交登录"""
        mock_driver = MagicMock()
        agent = AITestAgent(driver=mock_driver, app_identifier="demo_app")

        screen_info = {
            "elements": [
                {"text": "请输入短信验证码", "is_input": True, "center": [540, 600]},
                {"text": "确定登录", "center": [540, 800]}
            ]
        }

        clicked = []
        typed = []
        agent.executor._locate_and_click = lambda el, c: clicked.append(el.get("text"))
        agent.executor._locate_and_type = lambda el, t: typed.append((el.get("text"), t))

        with patch("ai_engine.screen_parser.ScreenParser.get_screen_summary", return_value={"elements": [{"text": "个人中心"}]}), \
             patch("ai_engine.screen_parser.ScreenParser.wait_for_visual_settling", return_value=True):
            res = agent._execute_sms_code_injection("654321", screen_info)

        self.assertTrue(res)
        self.assertEqual(typed, [("请输入短信验证码", "654321")])
        self.assertIn("确定登录", clicked)

    def test_08_task_manager_resolve_decision_supports_sms_code(self):
        """测试 8: TaskManager 正确处理并持久化短信验证码决策"""
        mgr = TaskManager()
        sid = "sess_unit_test_sms"
        mgr.sessions[sid] = {
            "session_id": sid,
            "status": "WAITING_USER_INPUT",
            "hitl_decision": {"mode": "sms_code"},
            "devices": {"dev1": {"action": "", "logs": []}}
        }

        payload = {
            "decision_type": "inject_sms",
            "sms_code": "888999"
        }
        res = mgr.resolve_decision(sid, payload)
        self.assertTrue(res)

        decision_file = ROOT / "scratch" / f"decision_{sid}.json"
        self.assertTrue(decision_file.exists())
        data = json.loads(decision_file.read_text(encoding="utf-8"))
        self.assertEqual(data["decision_type"], "inject_sms")
        self.assertEqual(data["sms_code"], "888999")
        try: decision_file.unlink()
        except Exception: pass


if __name__ == "__main__":
    unittest.main()
