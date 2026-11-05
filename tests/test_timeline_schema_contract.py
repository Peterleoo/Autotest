# -*- coding: utf-8 -*-
import unittest
from core.timeline_manager import TimelineManager


class TestTimelineSchemaContract(unittest.TestCase):
    def test_supported_block_validation(self):
        """测试合规的 Block 能够通过契约校验并补齐基础元数据"""
        raw_block = {
            "type": "thought",
            "bullets": [{"tag": "意图", "content": "测试步骤"}],
            "duration": "1.2s"
        }
        sanitized = TimelineManager.validate_and_sanitize_block(raw_block)
        self.assertEqual(sanitized["type"], "thought")
        self.assertTrue(sanitized["block_id"].startswith("blk_thought_"))
        self.assertIn("timestamp", sanitized)

    def test_unknown_block_fallback_sanitization(self):
        """测试未知异常 Block 安全降级为 system_notice，杜绝前端崩溃"""
        raw_block = {
            "type": "malicious_or_unknown_type",
            "content": "未经定义的黑天鹅类型"
        }
        sanitized = TimelineManager.validate_and_sanitize_block(raw_block)
        self.assertEqual(sanitized["type"], "system_notice")
        self.assertIn("未经定义的黑天鹅类型", sanitized["content"])

    def test_factory_methods_produce_valid_schema(self):
        """测试新增的工厂方法生成的结构符合契约规范"""
        # Suite Builder
        sb = TimelineManager.create_suite_builder_block(
            suite_data={"suite_title": "测试套件", "cases": []},
            session_id="sess_test_123"
        )
        self.assertEqual(sb["type"], "suite_builder")
        self.assertEqual(sb["block_id"], "suite_block_sess_test_123")
        self.assertIn(sb["type"], TimelineManager.SUPPORTED_BLOCK_TYPES)

        # Doc Mismatch Guard
        guard = TimelineManager.create_doc_mismatch_guard_block(
            session_id="sess_test_456",
            doc_name="spec.md",
            app_name="App",
            relevance_info={"is_relevant": False}
        )
        self.assertEqual(guard["type"], "doc_mismatch_guard")
        self.assertEqual(guard["block_id"], "guard_sess_test_456")
        self.assertIn(guard["type"], TimelineManager.SUPPORTED_BLOCK_TYPES)


if __name__ == '__main__':
    unittest.main()
