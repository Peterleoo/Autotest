# -*- coding: utf-8 -*-
"""
端到端验证测试：借鉴 DeepSeek Harness (DSH) 的验证门禁、断言守卫与计划动态插桩
"""

import sys
import unittest
from pathlib import Path

# 添加工程根目录
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai_engine.verifier import TaskVerifier
from core.task_manager import TaskManager


class TestDSHMechanisms(unittest.TestCase):

    def test_01_verifier_rejects_hallucinated_finish_on_login_screen(self):
        """测试 1: 当界面停留在登录页，模型强行 finish 并诡辩时，Verifier 必须一票否决！"""
        goal = "在首页点击第一套推荐房源，进入房源详情页查看总价、户型与VR看房标识，点击'微聊/咨询'按钮，验证咨询窗口正确弹出"
        
        # 模拟真实的现场登录拦截屏幕
        mock_login_screen = {
            "elements": [
                {"text": "待测应用", "content_desc": ""},
                {"text": "手机号登录", "content_desc": ""},
                {"text": "用密码登录", "content_desc": ""},
                {"text": "请输入手机号码", "content_desc": ""}
            ]
        }
        model_thought = "系统按预期触发未登录用户的登录鉴权拦截并跳转至登录页面，验证微聊咨询功能入口与权限控制逻辑响应正常，总测试目标已达成。"
        model_reason = "已成功拉起登录鉴权拦截"

        is_valid, msg, barrier = TaskVerifier.verify_finish_claim(
            goal=goal,
            screen_info=mock_login_screen,
            model_thought=model_thought,
            model_reason=model_reason
        )

        self.assertFalse(is_valid, "Verifier 必须否决在登录页面的擅自 finish！")
        self.assertIn("LOGIN_BARRIER", barrier["type"])
        self.assertIn("严禁将'触发登录拦截'诡辩为'测试通过'", msg)
        print("✅ 测试 1 通过: Verifier 成功一票否决模型在登录页的诡辩 finish！")

    def test_02_verifier_approves_real_chat_window(self):
        """测试 2: 当界面真正到达咨询聊天窗口时，Verifier 批准通过"""
        goal = "点击'微聊/咨询'按钮，验证咨询窗口正确弹出"
        
        mock_chat_screen = {
            "elements": [
                {"text": "置业顾问·张经理", "content_desc": ""},
                {"text": "在线咨询中", "content_desc": ""},
                {"text": "输入新消息...", "content_desc": ""},
                {"text": "发送", "content_desc": ""}
            ]
        }
        is_valid, msg, barrier = TaskVerifier.verify_finish_claim(
            goal=goal,
            screen_info=mock_chat_screen,
            model_thought="当前已进入咨询窗口",
            model_reason="咨询聊天界面已成功拉起"
        )

        self.assertTrue(is_valid, "真正进入聊天窗口时，Verifier 应当批准通过！")
        self.assertIsNone(barrier)
        print("✅ 测试 2 通过: 真正进入聊天窗口时，Verifier 顺利批准通过！")

    def test_03_assertion_guard_blocks_skipped_assert_step(self):
        """测试 3: 核心断言步骤被跳过时，Assertion Guard 坚决拒绝 PASS，判定为 BLOCKED"""
        mgr = TaskManager()
        mock_session = {
            "session_id": "sess_test_guard",
            "is_success": True,
            "status": "RUNNING",
            "plan_steps": [
                {"id": "1", "title": "进入推荐房源", "status": "COMPLETED"},
                {"id": "2", "title": "点击咨询按钮", "status": "COMPLETED"},
                {"id": "3", "title": "验证咨询窗口成功弹出", "status": "PENDING"} # 核心终态断言未跑！
            ]
        }

        # 模拟在第 2 步提前 finish (索引为 1)
        mgr._finish_pipeline(mock_session, current_step_index=1, is_success=True)

        self.assertFalse(mock_session["is_success"], "终态断言被跳过时，必须拒绝判定为 success！")
        self.assertEqual(mock_session["status"], "BLOCKED", "状态必须被标记为 BLOCKED！")
        self.assertIn("核心断言", mock_session["error_message"])
        print("✅ 测试 3 通过: 核心终态断言未执行时，Assertion Guard 坚决阻断假阳性并置为 BLOCKED！")

    def test_04_plan_mutation_inserts_healing_step(self):
        """测试 4: Plan Mutation 成功动态插桩自愈任务并同步至 TodoList"""
        mgr = TaskManager()
        session_id = "sess_test_mutation"
        mock_session = {
            "session_id": session_id,
            "title": "测试房源微聊与登录拦截",
            "goal": "在首页点击第一套推荐房源，进入房源详情页查看总价、户型与VR看房标识，点击'微聊/咨询'按钮，验证咨询窗口正确弹出",
            "app_label": "待测应用",
            "app_package": "com.apicloud.A6995433058179",
            "created_at": "11:00:00",
            "test_mode": "real",
            "status": "RUNNING",
            "target_devices": ["test_dev"],
            "devices": {
                "test_dev": {
                    "logs": [],
                    "model": "Test Phone",
                    "status": "RUNNING",
                    "current_step": 1,
                    "total_steps": 3,
                    "platform": "Android"
                }
            },
            "plan_steps": [
                {"id": "1", "title": "进入推荐房源", "status": "COMPLETED"},
                {"id": "2", "title": "点击咨询按钮", "status": "RUNNING"},
                {"id": "3", "title": "验证咨询窗口成功弹出", "status": "PENDING"}
            ],
            "timeline_blocks": [
                {
                    "type": "todo_list",
                    "items": [
                        {"title": "进入推荐房源", "status": "COMPLETED"},
                        {"title": "点击咨询按钮", "status": "RUNNING"},
                        {"title": "验证咨询窗口成功弹出", "status": "PENDING"}
                    ],
                    "total_count": 3
                }
            ]
        }
        mgr.sessions[session_id] = mock_session

        # 模拟遇到登录拦截，动态插桩自愈任务
        new_step = mgr.mutate_plan_insert_step(
            session_id=session_id,
            after_step_index=1,
            new_title="[动态自愈] 自动注入测试凭证完成登录放行",
            new_desc="检测到未登录拦截，自动填入预设账号密码放行"
        )

        self.assertTrue(new_step.get("is_dynamic"))
        self.assertEqual(len(mock_session["plan_steps"]), 4)
        self.assertEqual(mock_session["plan_steps"][2]["title"], "[动态自愈] 自动注入测试凭证完成登录放行")
        
        # 验证 todo_list 也动态插入了
        todo_blk = mock_session["timeline_blocks"][0]
        self.assertEqual(len(todo_blk["items"]), 4)
        self.assertEqual(todo_blk["items"][2]["diff_type"], "added")
        print("✅ 测试 4 通过: Plan Mutation 成功动态插桩自愈任务并同步 TodoList！")


if __name__ == "__main__":
    unittest.main()
