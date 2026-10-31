# -*- coding: utf-8 -*-
import unittest
import asyncio
from web.app import task_mgr, get_session_raw_logs_endpoint, save_session_to_local_case


class TestRawLogsAndSaveCase(unittest.TestCase):
    def setUp(self):
        self.session_id = "sess_1031_100648_1f45"

    def test_raw_logs_endpoint(self):
        """测试全量真实运行日志流接口"""
        response = asyncio.run(get_session_raw_logs_endpoint(self.session_id))
        self.assertEqual(response.status_code, 200)
        text = response.body.decode("utf-8")
        self.assertIn("自动化测试会话底层运行日志", text)
        self.assertIn("象盒找房", text)
        # 验证包含真机日志关键行
        self.assertIn("原生 ADB 会话结束", text)
        self.assertIn("Verifier 门禁批准", text)
        lines = [l for l in text.splitlines() if l.strip()]
        self.assertGreater(len(lines), 20)

    def test_session_detail_contains_logs(self):
        """测试 session 详情中 devices 包含了 full logs"""
        detail = task_mgr.get_session(self.session_id)
        self.assertIsNotNone(detail)
        devices = detail.get("devices", {})
        self.assertTrue(len(devices) > 0)
        dev = list(devices.values())[0]
        self.assertIn("logs", dev)
        self.assertGreater(len(dev["logs"]), 20)

    def test_save_to_local_case_endpoint(self):
        """测试保存本地用例接口及再次保存幂等性"""
        data = asyncio.run(save_session_to_local_case(self.session_id))
        self.assertTrue(data.get("success"))
        self.assertIn("filename", data)
        self.assertIn("module", data)
        self.assertTrue(bool(data.get("title")))

        # 再次保存应返回 already_saved 且保持 title
        data2 = asyncio.run(save_session_to_local_case(self.session_id))
        self.assertTrue(data2.get("success"))
        self.assertTrue(data2.get("already_saved"))
        self.assertTrue(bool(data2.get("title")))


if __name__ == "__main__":
    unittest.main()
