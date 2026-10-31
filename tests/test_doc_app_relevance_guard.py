# -*- coding: utf-8 -*-
import unittest
import time
from pathlib import Path
from core.test_spec_synthesizer import TestSpecSynthesizer
from core.task_manager import TaskManager, SESSIONS_STORE_DIR


class TestDocAppRelevanceGuard(unittest.TestCase):
    def setUp(self):
        self.mgr = TaskManager()
        self.created_sessions = []

    def tearDown(self):
        for sid in self.created_sessions:
            p = SESSIONS_STORE_DIR / f"{sid}.json"
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
            self.mgr.sessions.pop(sid, None)

    def test_relevance_detection_mismatch(self):
        """测试象盒找房与 Autotest 平台规格书的不匹配识别"""
        autotest_doc = """# Autotest 平台产品规格书
1. 核心定位：基于多模态大模型的 Android 移动端自动化测试平台与真机调试工具。
2. 架构模块：测试框架、真机调试、多模态驱动、知识库、截屏探针、推演执行。
3. 脚本固化：支持 pytest 脚本固化导出与 adb 离线脱机运行。
"""
        res = TestSpecSynthesizer.check_doc_app_relevance(
            doc_text=autotest_doc,
            app_name="象盒找房",
            app_package="com.example.xhhouse",
            app_label="象盒找房"
        )
        self.assertFalse(res["is_relevant"])
        self.assertIn("房产", res["app_domain"])
        self.assertIn("AI自动化测试", res["doc_domain"])
        self.assertLessEqual(res["relevance_score"], 30)

    def test_relevance_detection_match(self):
        """测试象盒找房与房产规格书的匹配识别"""
        house_doc = """# 象盒找房租房与委托功能规范
1. 房源检索：支持根据小区、商圈、租房、整租、合租以及户型进行多维筛选。
2. 房东委托：用户可在房东委托页面提交出租需求，平台经纪人跟进。
3. 看房预约：用户可以与房产经纪人发起微聊并预约看房时间。
"""
        res = TestSpecSynthesizer.check_doc_app_relevance(
            doc_text=house_doc,
            app_name="象盒找房",
            app_package="com.example.xhhouse",
            app_label="象盒找房"
        )
        self.assertTrue(res["is_relevant"])
        self.assertIn("房产", res["app_domain"])
        self.assertIn("房产", res["doc_domain"])
        self.assertGreaterEqual(res["relevance_score"], 80)

    def test_task_dispatch_guard_interception(self):
        """测试在创建会话时，若文档与应用不匹配，系统安全拦截并挂起为 AWAITING_USER_INPUT"""
        autotest_doc = """# Autotest 平台产品规格书
1. 核心定位：基于多模态大模型的 Android 移动端自动化测试平台与真机调试工具。
2. 架构模块：测试平台、真机调试、多模态驱动、截屏探针、推演执行。
3. 脚本固化：支持 pytest 脚本固化导出与 adb 离线脱机运行。
"""
        attachments = [
            {
                "filename": "Autotest-规格书.md",
                "extracted_text": autotest_doc,
                "is_doc": True,
                "is_image": False,
                "size": "500B"
            }
        ]

        sid = self.mgr.create_session(
            goal="请根据文档写测试用例完成测试",
            device_ids=["mock_dev_guard_test"],
            app_id="象盒找房",
            app_label="象盒找房",
            app_package="com.example.xhhouse",
            test_mode="local",
            approval_mode="auto",
            attachments=attachments
        )
        self.created_sessions.append(sid)

        # 等待后台派发线程判定门禁，应在 3 秒内完成拦截
        guard_triggered = False
        for _ in range(25):
            time.sleep(0.2)
            sess = self.mgr.get_session(sid)
            if sess:
                tb = sess.get("timeline_blocks", [])
                if any(b.get("type") == "doc_mismatch_guard" for b in tb):
                    guard_triggered = True
                    self.assertEqual(sess.get("status"), "AWAITING_USER_INPUT")
                    break

        self.assertTrue(guard_triggered, "不匹配文档应触发 doc_mismatch_guard 拦截")

    def test_force_run_bypasses_guard(self):
        """测试强制放行机制：调用 force_resume_doc_suite 成功绕过门禁并生成用例"""
        autotest_doc = """# Autotest 平台产品规格书
1. 测试平台核心定位与架构模块，支持 pytest 脚本固化与真机调试。
"""
        attachments = [
            {
                "filename": "Autotest-规格书.md",
                "extracted_text": autotest_doc,
                "is_doc": True,
                "is_image": False,
                "size": "500B"
            }
        ]

        sid = self.mgr.create_session(
            goal="请根据文档写测试用例完成测试",
            device_ids=["mock_dev_force_test"],
            app_id="象盒找房",
            app_label="象盒找房",
            app_package="com.example.xhhouse",
            test_mode="local",
            approval_mode="auto",
            attachments=attachments
        )
        self.created_sessions.append(sid)

        # 先等门禁拦截
        time.sleep(1.0)
        sess = self.mgr.get_session(sid)
        self.assertEqual(sess.get("status"), "AWAITING_USER_INPUT")

        # 触发强制放行接续
        res = self.mgr.force_resume_doc_suite(sid)
        self.assertTrue(res)

        # 验证是否越过门禁，进入用例提炼
        resumed = False
        for _ in range(40):
            time.sleep(0.2)
            s = self.mgr.get_session(sid)
            if s and s.get("is_systemic_suite"):
                resumed = True
                break

        self.assertTrue(resumed, "强制放行后应成功进入用例提炼与系统测试")


if __name__ == '__main__':
    unittest.main()
