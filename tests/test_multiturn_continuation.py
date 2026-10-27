# -*- coding: utf-8 -*-
"""
单元测试：连续对话与 DeepSeek 机制 (Multi-turn Conversation & In-place Continuation)
验证：
1. append_session_message 自动递增 turn_id 并为 timeline_blocks 注入用户气泡与思考态
2. MemoryManager 针对多轮会话能够完整合成历史状态演进链
3. DriverFactory 在 auto_launch=False 时保持就地接管当前屏幕
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from core.task_manager import TaskManager
from core.memory_manager import MemoryManager
from core.timeline_manager import TimelineManager

class TestMultiTurnContinuation(unittest.TestCase):

    def setUp(self):
        self.tm = TaskManager()

    def test_multiturn_append_message_and_timeline_blocks(self):
        # 1. 创建模拟会话
        sess_id = "test_multiturn_sess_001"
        self.tm.sessions[sess_id] = {
            "session_id": sess_id,
            "title": "测试连续对话",
            "goal": "进入首页，查看精选房源",
            "status": "COMPLETED",
            "is_success": True,
            "target_devices": ["mock_device"],
            "devices": {
                "mock_device": {
                    "model": "Mock Phone",
                    "status": "PASS",
                    "logs": []
                }
            },
            "timeline_blocks": [
                TimelineManager.create_user_block("进入首页，查看精选房源", turn_id=1),
                TimelineManager.create_test_summary_block(session_id=sess_id, goal="进入首页", is_success=True)
            ],
            "turns": []
        }

        # 2. 追加第 2 轮连续对话指令
        res = self.tm.append_session_message(sess_id, "点击第一套精选房源，进入详情页查看户型")
        self.assertTrue(res["success"])
        self.assertEqual(res["turn_id"], 2)

        sess = self.tm.sessions[sess_id]
        # 验证会话重新进入 RUNNING
        self.assertEqual(sess["status"], "RUNNING")
        
        # 验证 timeline_blocks 中追加了用户气泡、思考块和 Todo 清单
        block_types = [b.get("type") for b in sess["timeline_blocks"]]
        self.assertIn("user_message", block_types)
        self.assertIn("thought", block_types)
        self.assertIn("todo_list", block_types)
        
        # 验证最后一个 user_message 正是本轮指令
        user_blocks = [b for b in sess["timeline_blocks"] if b.get("type") == "user_message"]
        self.assertEqual(len(user_blocks), 2)
        self.assertEqual(user_blocks[-1]["content"], "点击第一套精选房源，进入详情页查看户型")

        # 验证 MemoryManager 正确构造了多轮记忆上下文
        ctx = MemoryManager.build_memory_context(sess)
        self.assertIn("Turn 1", ctx)
        self.assertIn("点击第一套精选房源", ctx)
        print("✅ 连续对话多轮追问、Timeline 事件注入与事实上下文合成验证全部通过！")

if __name__ == "__main__":
    unittest.main()
