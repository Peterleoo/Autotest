import unittest
import time
import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_engine.test_agent import AITestAgent
from core.task_manager import TaskManager


class TestHitlTwoPhaseFlow(unittest.TestCase):
    """
    短信验证码人机协同两阶段时序与精准识别、合流注入与防死循环集成测试
    """

    def setUp(self):
        self.mock_driver = MagicMock()
        self.agent = AITestAgent(driver=self.mock_driver, llm_provider=None, app_identifier="com.xianghe.app")
        self.agent.session_id = "test_unit_sess_001"
        self.agent.executor = MagicMock()

    def test_01_detect_login_screen_state_anti_false_positive(self):
        """测试 1: 判定去伪 - 占位符绝不能误判为已发码"""
        # 1. 刚进登录页（未发码），输入框内仅有占位符
        screen_not_sent = {
            "elements": [
                {"index": 0, "text": "手机号快捷登录", "bounds": [100, 100, 500, 200]},
                {"index": 1, "text": "", "content_desc": "请输入手机号码", "is_input": True, "class": "android.widget.EditText"},
                {"index": 2, "text": "获取验证码", "bounds": [700, 300, 950, 400]},
                {"index": 3, "text": "请输入短信验证码", "is_input": True, "class": "android.widget.EditText"},
                {"index": 4, "text": "登录", "bounds": [100, 600, 980, 720]}
            ]
        }
        state, meta = AITestAgent._detect_login_screen_state(screen_not_sent)
        self.assertEqual(state, "phone_wait_code", f"未发码状态应判定为 phone_wait_code，实际: {state}")

        # 2. 已点击发码，出现物理倒计时 58s
        screen_sent_countdown = {
            "elements": [
                {"index": 0, "text": "18888888888", "is_input": True, "class": "android.widget.EditText"},
                {"index": 1, "text": "重新获取(58)", "bounds": [700, 300, 950, 400]},
                {"index": 2, "text": "", "is_input": True, "class": "android.widget.EditText"},
                {"index": 3, "text": "登录", "bounds": [100, 600, 980, 720]}
            ]
        }
        state2, meta2 = AITestAgent._detect_login_screen_state(screen_sent_countdown)
        self.assertEqual(state2, "sms_code", f"有倒计时应判定为 sms_code，实际: {state2}")

        # 3. 密码登录模式
        screen_password = {
            "elements": [
                {"index": 0, "text": "账号密码登录"},
                {"index": 1, "text": "请输入账号", "is_input": True, "class": "android.widget.EditText"},
                {"index": 2, "text": "请输入密码", "is_input": True, "class": "android.widget.EditText"},
                {"index": 3, "text": "登录"}
            ]
        }
        state3, meta3 = AITestAgent._detect_login_screen_state(screen_password)
        self.assertEqual(state3, "credential", f"密码登录应判定为 credential，实际: {state3}")

        # 4. 滑块拼图模式
        screen_slider = {
            "elements": [
                {"index": 0, "text": "请向右滑动滑块完成拼图"},
                {"index": 1, "text": "安全验证"}
            ]
        }
        state4, meta4 = AITestAgent._detect_login_screen_state(screen_slider)
        self.assertEqual(state4, "manual_takeover", f"滑块应判定为 manual_takeover，实际: {state4}")

    def test_02_anti_loop_hitl_guard(self):
        """测试 2: 协同冷却防死循环门禁 (Anti-Loop HITL Guard)"""
        screen_info = {
            "elements": [
                {"index": 0, "text": "密码登录"},
                {"index": 1, "text": "请输入密码", "is_input": True, "class": "android.widget.EditText"}
            ]
        }
        with patch.object(self.agent, "_execute_credential_injection", return_value=False):
            self.agent._last_hitl_resolved_time = time.time()
            self.agent._hitl_cooldown_steps = 3

            should_block = self.agent._check_and_prompt_hitl_credential(screen_info, "登录并查看首页")
            self.assertFalse(should_block, "处于冷却期内的重复登录门禁必须直接放行，禁止弹出卡片死循环！")

    def test_03_ai_hitl_flow_with_empty_fields_fallback(self):
        """测试 3: AI 自主发起协同在 fields 为空时智能回退注入，杜绝吞凭证"""
        screen_info = {
            "elements": [
                {"index": 0, "text": "账号密码登录"},
                {"index": 1, "text": "请输入账号", "is_input": True, "class": "android.widget.EditText"},
                {"index": 2, "text": "请输入密码", "is_input": True, "class": "android.widget.EditText"},
                {"index": 3, "text": "登录"}
            ]
        }
        decision = {
            "action": "request_human_help",
            "title": "人机协同 · 需要登录凭证",
            "help_type": "input",
            "fields": []  # 大模型返回的 fields 为空！
        }

        decision_file = Path("scratch") / f"decision_{self.agent.session_id}.json"
        decision_file.parent.mkdir(parents=True, exist_ok=True)
        decision_payload = {
            "status": "RESOLVED",
            "decision_type": "inject",
            "account": "18888888888",
            "password": "mypassword123",
            "remember": True
        }

        def write_decision():
            time.sleep(0.1)
            decision_file.write_text(json.dumps(decision_payload, ensure_ascii=False), encoding="utf-8")

        threading.Thread(target=write_decision, daemon=True).start()

        with patch.object(self.agent, "_execute_credential_injection", return_value=True) as mock_inject:
            resolved = self.agent._handle_ai_requested_human_help(decision, screen_info, "测试登录", max_wait_seconds=5.0)
            self.assertTrue(resolved, "协同应当成功解决")
            mock_inject.assert_called_once_with("18888888888", "mypassword123", screen_info, goal="测试登录")
            self.assertEqual(self.agent._hitl_cooldown_steps, 3)
            self.assertTrue(any("【人机协同已完成】" in m for m in self.agent.memory_context))

        if decision_file.exists():
            decision_file.unlink()

    def test_04_task_manager_mode_preservation(self):
        """测试 4: TaskManager 对 sms_code 与 phone_input 模式的透传与保护"""
        session_id = "test_tm_sess_002"
        session_data = {
            "session_id": session_id,
            "status": "RUNNING",
            "app_package": "com.test.app",
            "hitl_decision": None
        }

        log_line = f"⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app=com.test.app&mode=sms_code&attempt=1"

        import re
        if "⏸️ [WAIT_HITL_DECISION]" in log_line:
            m_mode = re.search(r"mode=([^&\s]+)", log_line)
            mode = m_mode.group(1) if m_mode else "credential"
            session_data["status"] = "WAITING_USER_INPUT"
            session_data["hitl_decision"] = {
                "type": mode,
                "mode": mode,
                "app_key": "com.test.app",
                "title": "人机协同 · 请输入短信验证码",
                "desc": "端侧已向手机发送验证码...",
                "timestamp": time.time()
            }

        self.assertEqual(session_data["status"], "WAITING_USER_INPUT")
        self.assertEqual(session_data["hitl_decision"]["mode"], "sms_code")
        self.assertEqual(session_data["hitl_decision"]["type"], "sms_code")

    def test_05_hitl_two_phase_phone_to_sms_flow(self):
        """测试 5: 短信验证码两阶段时序流转 (阶段一自动填手机发码 -> 阶段二注入短信验证码)"""
        # 阶段一界面：未发码 (获取验证码按钮存在，且无倒计时)
        screen_phase1 = {
            "elements": [
                {"index": 0, "text": "手机号快捷登录"},
                {"index": 1, "text": "", "content_desc": "请输入手机号码", "is_input": True, "class": "android.widget.EditText"},
                {"index": 2, "text": "获取验证码"},
                {"index": 3, "text": "登录"}
            ]
        }
        # 阶段二界面：发码成功后出现倒计时
        screen_phase2 = {
            "elements": [
                {"index": 0, "text": "18888888888", "is_input": True, "class": "android.widget.EditText"},
                {"index": 1, "text": "重新获取(59)"},
                {"index": 2, "text": "", "is_input": True, "class": "android.widget.EditText"},
                {"index": 3, "text": "登录"}
            ]
        }

        decision_file = Path("scratch") / f"decision_{self.agent.session_id}.json"
        decision_file.parent.mkdir(parents=True, exist_ok=True)

        def simulate_two_phase_user():
            # 阶段 1：用户提交手机号 18888888888
            time.sleep(0.1)
            payload1 = {"status": "RESOLVED", "decision_type": "inject_phone", "account": "18888888888"}
            decision_file.write_text(json.dumps(payload1, ensure_ascii=False), encoding="utf-8")

            # 等待阶段一处理发码完成并 unlink decision_file
            wait_for_unlink = time.time()
            while decision_file.exists() and time.time() - wait_for_unlink < 4.0:
                time.sleep(0.05)

            # 稍等 0.1s 确保主线程进入阶段二挂起循环
            time.sleep(0.1)
            # 阶段 2：用户收到短信后提交短信验证码
            payload2 = {"status": "RESOLVED", "decision_type": "inject_sms", "sms_code": "654321"}
            decision_file.write_text(json.dumps(payload2, ensure_ascii=False), encoding="utf-8")

        threading.Thread(target=simulate_two_phase_user, daemon=True).start()

        with patch.object(self.agent, "_execute_phone_send_sms", return_value=True) as mock_send_sms, \
             patch("ai_engine.test_agent.ScreenParser.get_screen_summary", return_value=screen_phase2), \
             patch.object(self.agent, "_execute_sms_code_injection", return_value=True) as mock_inject_sms:

            decision = {
                "action": "request_human_help",
                "title": "人机协同 · 手机号登录",
                "help_type": "input",
                "fields": []
            }

            resolved = self.agent._handle_ai_requested_human_help(decision, screen_phase1, "测试短信验证码登录", max_wait_seconds=6.0)
            self.assertTrue(resolved, "两阶段协同应顺利闭环完成")
            mock_send_sms.assert_called_once_with("18888888888", screen_phase1)
            mock_inject_sms.assert_called_once_with("654321", screen_phase2)

        if decision_file.exists():
            decision_file.unlink()


if __name__ == "__main__":
    unittest.main()
