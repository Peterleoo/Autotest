# -*- coding: utf-8 -*-
"""
AI 自主生成人机协作（AI-Generated HITL）与 Generative UI 单元测试
"""

import sys
import unittest
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai_engine.test_agent import AITestAgent
from core.task_manager import TaskManager


class TestAIGeneratedHITL(unittest.TestCase):

    def test_01_ai_requested_human_help_saves_dynamic_schema(self):
        """测试 1: AI 自主发起的 request_human_help 能够正确持久化动态 Schema"""
        mock_driver = MagicMock()
        agent = AITestAgent(driver=mock_driver, app_identifier="demo_app", session_id="sess_test_ai_hitl_01")

        ai_decision = {
            "thought": "当前界面需要输入动态短信验证码",
            "action": "request_human_help",
            "help_type": "input",
            "title": "人机协同 · 请输入短信验证码",
            "reason": "端侧已向手机发送短信验证码，AI无法凭空推导真实动态码",
            "description": "请查看手机短信并在下方输入：",
            "fields": [
              {
                "key": "sms_code",
                "label": "短信验证码",
                "placeholder": "请输入6位验证码",
                "type": "text",
                "target_index": 3
              }
            ],
            "action_button_text": "填入并继续"
        }

        mock_screen = {
            "elements": [
                {"index": 1, "text": "手机号登录"},
                {"index": 2, "text": "18888888888"},
                {"index": 3, "text": "请输入验证码", "is_input": True, "center": [540, 600]},
                {"index": 4, "text": "确定登录", "center": [540, 800]}
            ]
        }

        # 模拟 0.1 秒后用户通过 decision 文件返回验证码
        decision_file = ROOT / "scratch" / f"decision_{agent.session_id}.json"
        
        def fake_user_response():
            time.sleep(0.1)
            decision_file.parent.mkdir(parents=True, exist_ok=True)
            decision_file.write_text(json.dumps({
                "status": "RESOLVED",
                "decision_type": "ai_submit",
                "inputs": {"sms_code": "654321"}
            }), encoding="utf-8")

        import threading
        t = threading.Thread(target=fake_user_response)
        t.start()

        typed_entries = []
        clicked_entries = []
        agent.executor._locate_and_type = lambda el, val: typed_entries.append((el.get("index"), val))
        agent.executor._locate_and_click = lambda el, c: clicked_entries.append(el.get("text"))

        res = agent._handle_ai_requested_human_help(ai_decision, mock_screen, "登录测试")
        t.join()

        self.assertTrue(res, "AI 人机协同处理流程必须顺利返回 True！")
        # 验证是否精准上屏到 target_index = 3 的组件
        self.assertEqual(typed_entries, [(3, "654321")], "必须准确将 AI 动态字段填入 target_index 对应输入框！")
        # 验证是否自动点击了提交按钮
        self.assertIn("确定登录", clicked_entries, "填入后必须自动点击提交按钮！")

    def test_02_ai_requested_human_help_choice_flow(self):
        """测试 2: AI 发起 choice 选项时，用户选择后系统自动点击对应选项"""
        mock_driver = MagicMock()
        agent = AITestAgent(driver=mock_driver, app_identifier="demo_app", session_id="sess_test_ai_hitl_02")

        ai_decision = {
            "thought": "端侧展示了多门店选择弹窗",
            "action": "request_human_help",
            "help_type": "choice",
            "title": "人机协同 · 请选择目标门店",
            "reason": "需要人工选择测试门店",
            "options": ["长沙开福店", "天心分部", "岳麓总部"]
        }

        mock_screen = {
            "elements": [
                {"index": 1, "text": "请选择门店"},
                {"index": 2, "text": "长沙开福店", "center": [300, 400]},
                {"index": 3, "text": "天心分部", "center": [300, 500]}
            ]
        }

        decision_file = ROOT / "scratch" / f"decision_{agent.session_id}.json"
        
        def fake_user_choice():
            time.sleep(0.1)
            decision_file.parent.mkdir(parents=True, exist_ok=True)
            decision_file.write_text(json.dumps({
                "status": "RESOLVED",
                "decision_type": "ai_choice",
                "choice": "长沙开福店"
            }), encoding="utf-8")

        import threading
        t = threading.Thread(target=fake_user_choice)
        t.start()

        clicked = []
        agent.executor._locate_and_click = lambda el, c: clicked.append(el.get("text"))

        res = agent._handle_ai_requested_human_help(ai_decision, mock_screen, "选择门店测试")
        t.join()

        self.assertTrue(res)
        self.assertIn("长沙开福店", clicked, "必须自动点击用户选中的选项！")

    def test_03_task_manager_resolve_ai_generated_payload(self):
        """测试 3: TaskManager 能够接收 dynamic inputs 并写入通信文件"""
        mgr = TaskManager()
        sid = "sess_ai_tm_test"
        mgr.sessions[sid] = {
            "session_id": sid,
            "status": "WAITING_USER_INPUT",
            "hitl_decision": {
                "type": "ai_generated",
                "title": "AI动态协同"
            },
            "devices": {"dev1": {"action": "", "logs": []}}
        }

        payload = {
            "decision_type": "ai_submit",
            "inputs": {
                "user_token": "token_999",
                "sms_code": "112233"
            }
        }
        res = mgr.resolve_decision(sid, payload)
        self.assertTrue(res)

        decision_file = ROOT / "scratch" / f"decision_{sid}.json"
        self.assertTrue(decision_file.exists())
        data = json.loads(decision_file.read_text(encoding="utf-8"))
        self.assertEqual(data["decision_type"], "ai_submit")
        self.assertEqual(data["inputs"]["user_token"], "token_999")
        self.assertEqual(data["inputs"]["sms_code"], "112233")
        try: decision_file.unlink()
        except Exception: pass


if __name__ == "__main__":
    unittest.main()
