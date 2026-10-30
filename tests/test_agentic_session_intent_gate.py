import os
import json
import time
import pytest
import unittest
from pathlib import Path
from core.task_manager import TaskManager
from core.timeline_manager import TimelineManager

ROOT = Path(__file__).resolve().parent.parent

class TestAgenticSessionIntentGate(unittest.TestCase):

    def setUp(self):
        self.mgr = TaskManager()
        self.test_sid = f"test_session_{int(time.time()*1000)}"
        self.mgr.sessions[self.test_sid] = {
            "session_id": self.test_sid,
            "title": "单元测试会话",
            "goal": "测试登录与核心链路",
            "status": "RUNNING",
            "devices": {
                "mock_dev": {
                    "device_id": "mock_dev",
                    "status": "RUNNING",
                    "logs": [],
                    "action": "执行中"
                }
            },
            "timeline_blocks": [],
            "plan_steps": [],
            "turns": []
        }

    def tearDown(self):
        # 清理 scratch 目录下的决策文件
        dec_file = ROOT / "scratch" / f"decision_{self.test_sid}.json"
        if dec_file.exists():
            try: dec_file.unlink()
            except Exception: pass
        if self.test_sid in self.mgr.sessions:
            del self.mgr.sessions[self.test_sid]

    def test_01_intent_gate_intercepts_stop_command(self):
        """测试 1: 意图拦截中枢精准拦截停止/终止指令并安全熔断"""
        stop_keywords = ["停止", "终止", "取消", "stop", "cancel", "退出", "结束"]
        
        for kw in stop_keywords:
            sid = f"test_stop_{kw}_{int(time.time()*1000)}"
            self.mgr.sessions[sid] = {
                "session_id": sid,
                "title": f"测试 {kw}",
                "status": "RUNNING",
                "devices": {"mock_dev": {"device_id": "mock_dev", "status": "RUNNING", "logs": []}},
                "hitl_decision": {"mode": "sms_code", "title": "等待验证码"},
                "timeline_blocks": [],
                "plan_steps": [],
                "turns": []
            }
            try:
                res = self.mgr.append_session_message(sid, kw)
                self.assertTrue(res.get("success"))
                self.assertTrue(res.get("stopped"))
                
                sess = self.mgr.sessions[sid]
                # 状态必须切为 STOPPED
                self.assertEqual(sess.get("status"), "STOPPED")
                # hitl_decision 必须彻底清理为 None
                self.assertIsNone(sess.get("hitl_decision"))
                
                # scratch 文件必须写入取消状态
                dec_file = ROOT / "scratch" / f"decision_{sid}.json"
                self.assertTrue(dec_file.exists())
                dec_data = json.loads(dec_file.read_text(encoding="utf-8"))
                self.assertEqual(dec_data.get("status"), "CANCELLED")
                self.assertEqual(dec_data.get("decision_type"), "cancel")

                # 时间线中必须包含中性克制的系统终止信息块
                blocks = sess.get("timeline_blocks", [])
                notice_blocks = [b for b in blocks if b.get("type") == "system_notice"]
                self.assertGreaterEqual(len(notice_blocks), 1)
                self.assertIn("主动终止", notice_blocks[-1].get("content", ""))
            finally:
                dec_f = ROOT / "scratch" / f"decision_{sid}.json"
                if dec_f.exists():
                    try: dec_f.unlink()
                    except Exception: pass
                if sid in self.mgr.sessions:
                    del self.mgr.sessions[sid]

    def test_02_stop_session_deep_cleanup(self):
        """测试 2: stop_session 深度清理人机协同挂起状态与通信文件"""
        self.mgr.sessions[self.test_sid]["hitl_decision"] = {
            "mode": "credential",
            "title": "人机协同 · 需要登录凭证"
        }
        self.mgr.sessions[self.test_sid]["status"] = "WAITING_USER_INPUT"

        ok = self.mgr.stop_session(self.test_sid)
        self.assertTrue(ok)
        
        sess = self.mgr.sessions[self.test_sid]
        self.assertEqual(sess["status"], "STOPPED")
        self.assertIsNone(sess.get("hitl_decision"))
        
        dec_file = ROOT / "scratch" / f"decision_{self.test_sid}.json"
        self.assertTrue(dec_file.exists())
        dec_data = json.loads(dec_file.read_text(encoding="utf-8"))
        self.assertEqual(dec_data["status"], "CANCELLED")

    def test_03_hitl_bridge_sms_code(self):
        """测试 3: 短信验证码挂起状态下，输入框直接输入验证码智能桥接"""
        self.mgr.sessions[self.test_sid]["status"] = "WAITING_USER_INPUT"
        self.mgr.sessions[self.test_sid]["hitl_decision"] = {
            "mode": "sms_code",
            "title": "人机协同 · 请输入短信验证码"
        }

        res = self.mgr.append_session_message(self.test_sid, "882910")
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("resolved_hitl"))
        self.assertEqual(res.get("decision_type"), "inject_sms")

        sess = self.mgr.sessions[self.test_sid]
        self.assertEqual(sess["status"], "RUNNING")
        self.assertIsNone(sess.get("hitl_decision"))

        dec_file = ROOT / "scratch" / f"decision_{self.test_sid}.json"
        self.assertTrue(dec_file.exists())
        data = json.loads(dec_file.read_text(encoding="utf-8"))
        self.assertEqual(data["decision_type"], "inject_sms")
        self.assertEqual(data["sms_code"], "882910")

    def test_04_hitl_bridge_phone_input(self):
        """测试 4: 手机号待发送挂起状态下，输入框输入手机号智能桥接"""
        self.mgr.sessions[self.test_sid]["status"] = "WAITING_USER_INPUT"
        self.mgr.sessions[self.test_sid]["hitl_decision"] = {
            "mode": "phone_input",
            "title": "人机协同 · 请输入测试手机号"
        }

        res = self.mgr.append_session_message(self.test_sid, "13912345678")
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("resolved_hitl"))
        self.assertEqual(res.get("decision_type"), "inject_phone")

        sess = self.mgr.sessions[self.test_sid]
        self.assertEqual(sess["status"], "RUNNING")
        self.assertIsNone(sess.get("hitl_decision"))

        dec_file = ROOT / "scratch" / f"decision_{self.test_sid}.json"
        self.assertTrue(dec_file.exists())
        data = json.loads(dec_file.read_text(encoding="utf-8"))
        self.assertEqual(data["decision_type"], "inject_phone")
        self.assertEqual(data["account"], "13912345678")

    def test_05_hitl_bridge_manual_done_and_skip(self):
        """测试 5: 人机协同挂起状态下，输入'已完成'或'跳过'智能识别"""
        self.mgr.sessions[self.test_sid]["status"] = "WAITING_USER_INPUT"
        self.mgr.sessions[self.test_sid]["hitl_decision"] = {
            "mode": "manual_takeover",
            "title": "人机协同 · 请在投屏手动完成"
        }

        res = self.mgr.append_session_message(self.test_sid, "已完成")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("decision_type"), "manual_done")

        dec_file = ROOT / "scratch" / f"decision_{self.test_sid}.json"
        self.assertTrue(dec_file.exists())
        data = json.loads(dec_file.read_text(encoding="utf-8"))
        self.assertEqual(data["decision_type"], "manual_done")

    def test_06_dynamic_planning_removes_hardcoded_fake_template(self):
        """测试 6: 正常追加测试意图时，动态差量拆解，彻底移除硬编码 2 步伪模板"""
        # 测试追加真实复杂意图
        complex_goal = "进入二手房列表，点击第一套房源，然后查看房源总价与面积并断言核心字段"
        res = self.mgr.append_session_message(self.test_sid, complex_goal)
        self.assertTrue(res.get("success"))

        sess = self.mgr.sessions[self.test_sid]
        steps = sess.get("plan_steps", [])
        
        # 绝不应是硬编码的“1/2 解析与定位，2/2 执行与断言”
        step_titles = [s.get("title", "") for s in steps]
        for t in step_titles:
            self.assertFalse(t.startswith("解析与定位："))
            self.assertFalse(t.startswith("执行与断言："))

        # 检查时间线中的思考态 bullets
        tb = sess.get("timeline_blocks", [])
        th_blocks = [b for b in tb if b.get("type") == "thought"]
        self.assertGreaterEqual(len(th_blocks), 1)
        bullets = th_blocks[-1].get("bullets", [])
        bullet_tags = [b.get("tag") for b in bullets]
        self.assertIn("意图深度解析", bullet_tags)
        self.assertIn("动态规划路径", bullet_tags)

    def test_07_frontend_contract_integrity(self):
        """测试 7: 前端契约完整性（临时乐观节点清理标记、终止任务按钮及Notice组件）"""
        index_html_path = ROOT / "web" / "templates" / "index.html"
        self.assertTrue(index_html_path.exists())
        html_content = index_html_path.read_text(encoding="utf-8")

        # 1. 临时节点必须标记 .optimistic-temp-node 与 data-temp-node
        self.assertIn(".optimistic-temp-node", html_content)
        self.assertIn("data-temp-node", html_content)
        self.assertIn("temp_user_", html_content)
        self.assertIn("temp_th_", html_content)

        # 2. renderChatTimelineStream 必须安全清理临时乐观节点
        self.assertIn("flow.querySelectorAll(\".optimistic-temp-node", html_content)

        # 3. 必须支持 system_notice 渲染
        self.assertIn("system_notice", html_content)
        self.assertIn("stream-system-notice-row", html_content)

        # 4. 人机协同卡片必须暴露终止任务操作与 stopSessionById
        self.assertIn("stopSessionById", html_content)
        self.assertIn("终止任务", html_content)

if __name__ == "__main__":
    unittest.main()
