# -*- coding: utf-8 -*-
import unittest
from ai_engine.screen_parser import ScreenParser
from ai_engine.action_executor import ActionExecutor


class TestCompactRefSnapshot(unittest.TestCase):
    def setUp(self):
        self.sample_elements = [
            # 1. 纯布局容器（无文本、无ID、不可点击）-> 应被智能过滤
            {
                "index": 1,
                "class": "android.widget.FrameLayout",
                "text": "",
                "desc": "",
                "resource_id": "",
                "clickable": False,
                "center": [540, 1000]
            },
            # 2. 按钮 -> 应该被保留为 Button
            {
                "index": 2,
                "class": "android.widget.Button",
                "text": "立即登录",
                "desc": "",
                "resource_id": "com.example.app:id/btn_login",
                "clickable": True,
                "center": [540, 1200]
            },
            # 3. 输入框 -> 应该被保留为 Input
            {
                "index": 3,
                "class": "android.widget.EditText",
                "text": "",
                "desc": "请输入手机号",
                "resource_id": "com.example.app:id/et_phone",
                "clickable": True,
                "center": [540, 950]
            },
            # 4. 纯文本标题 -> 应该被保留为 Text
            {
                "index": 4,
                "class": "android.widget.TextView",
                "text": "欢迎使用应用",
                "desc": "",
                "resource_id": "",
                "clickable": False,
                "center": [540, 400]
            }
        ]

    def test_compact_snapshot_filtering_and_indexing(self):
        """测试紧凑快照去噪与符号分配"""
        text, ref_map = ScreenParser.generate_compact_ref_snapshot(self.sample_elements)

        # 验证 FrameLayout 被过滤，只剩 3 个有效语义控件
        self.assertEqual(len(ref_map), 3)
        self.assertIn("@e1", ref_map)
        self.assertIn("@e2", ref_map)
        self.assertIn("@e3", ref_map)

        # 验证 @e1 是 Button 且文本正确
        e1 = ref_map["@e1"]
        self.assertEqual(e1["text"], "立即登录")
        self.assertEqual(e1["center"], [540, 1200])

        # 验证 @e2 是 Input
        e2 = ref_map["@e2"]
        self.assertEqual(e2["desc"], "请输入手机号")

        # 验证输出文本紧凑格式
        self.assertIn('@e1 [Button "立即登录"', text)
        self.assertIn('@e2 [Input desc="请输入手机号"', text)
        self.assertIn('@e3 [Text "欢迎使用应用"', text)

    def test_action_executor_resolves_ref_symbol(self):
        """测试 ActionExecutor 能够通过 ref 字段定位目标元素"""
        # 使用 mock 驱动
        class MockDriver:
            def __init__(self):
                self.tapped = []
            def execute_adb(self, cmd):
                self.tapped.append(cmd)
            def get_window_size(self):
                return {"width": 1080, "height": 2160}

        driver = MockDriver()
        executor = ActionExecutor(driver=driver)

        _, ref_map = ScreenParser.generate_compact_ref_snapshot(self.sample_elements)
        elements_list = list(ref_map.values())

        # 1. 使用 ref="@e1" 点击
        res = executor.execute({"action": "tap", "ref": "@e1", "reason": "测试点击登录"}, elements_list)
        self.assertTrue(res["success"])
        # 验证点击了 (540, 1200)
        self.assertTrue(any("540" in str(cmd) and "1200" in str(cmd) for cmd in driver.tapped))

        # 2. 向下兼容：使用数字 target_index=2 点击（对应 sample_elements 的原始 index 2）
        res2 = executor.execute({"action": "tap", "target_index": 2, "reason": "测试数字索引点击"}, elements_list)
        self.assertTrue(res2["success"])


if __name__ == '__main__':
    unittest.main()
