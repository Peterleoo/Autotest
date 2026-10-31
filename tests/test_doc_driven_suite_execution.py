# -*- coding: utf-8 -*-
import unittest
import time
from pathlib import Path
from core.task_manager import TaskManager, SESSIONS_STORE_DIR


class TestDocDrivenSuiteExecution(unittest.TestCase):
    def setUp(self):
        self.mgr = TaskManager()
        self.created_sessions = []

    def tearDown(self):
        # 彻底自清理测试中生成的临时会话，杜绝污染正式界面任务列表
        for sid in self.created_sessions:
            p = SESSIONS_STORE_DIR / f"{sid}.json"
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
            self.mgr.sessions.pop(sid, None)

    def test_create_session_with_doc_attachment_auto_synthesizes_and_runs(self):
        """测试上传需求文档附件后，系统自动触发用例提炼、挂载 Suite Builder 卡片并启动系统级测试"""
        doc_sample = """# 象盒找房用户登录与订单业务规约
## 1. 账号登录授权
用户进入个人中心，未登录时点击登录，输入手机号和短信验证码完成登录。
## 2. 核心房源搜索
在首页顶部搜索栏输入商圈或房源关键词，进入列表下拉刷新并上拉加载。
## 3. 房东委托发布表单
进入房东委托页面，输入小区名称与联系电话，验证必填拦截。
"""
        attachments = [
            {
                "filename": "业务需求规格说明书.md",
                "extracted_text": doc_sample,
                "is_doc": True,
                "is_image": False,
                "size": "500B"
            }
        ]

        sid = self.mgr.create_session(
            goal="请根据文档写测试用例完成测试",
            device_ids=["mock_device_doc_suite"],
            test_mode="local",
            approval_mode="auto",
            attachments=attachments
        )
        self.created_sessions.append(sid)

        # 异步线程调用 LLM 提炼用例并分发，等待最多 12 秒
        sess = None
        for _ in range(60):
            sess = self.mgr.get_session(sid)
            if sess and sess.get("is_systemic_suite"):
                break
            time.sleep(0.2)

        self.assertIsNotNone(sess)
        self.assertTrue(sess.get("is_systemic_suite"), "会话应被自动标记为系统级用例套件模式")
        
        # 验证步骤是从文档中提炼出来的真实用例，而不是普通的默认单步
        plan_steps = sess.get("plan_steps", [])
        self.assertGreaterEqual(len(plan_steps), 2, "应至少从文档中提炼出 2 个用例步骤")
        print("\nSynthesized Plan Steps:", [s.get("title") for s in plan_steps])

        # 验证时间线块中包含了 suite_builder Generative UI 编排卡片
        tb = sess.get("timeline_blocks", [])
        suite_cards = [b for b in tb if b.get("type") == "suite_builder"]
        self.assertEqual(len(suite_cards), 1, "时间线流中必须挂载 suite_builder 编排卡片")
        suite_data = suite_cards[0].get("suite_data", {})
        self.assertGreaterEqual(len(suite_data.get("cases", [])), 2)

        # 等待串联执行完成
        for _ in range(50):
            sess = self.mgr.get_session(sid)
            if sess and sess.get("status") in ["READY_FOR_REVIEW", "COMPLETED", "FAILED"]:
                break
            time.sleep(0.2)

        self.assertEqual(sess.get("status"), "READY_FOR_REVIEW")
        self.assertTrue(sess.get("is_success"))


if __name__ == "__main__":
    unittest.main()
