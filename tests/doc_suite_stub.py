# -*- coding: utf-8 -*-
"""文档驱动用例提炼的离线桩：避免单测依赖真实 LLM 网络时延（实测可达 50s+）"""
from typing import Any, Dict, Optional
from unittest import TestCase
from unittest.mock import patch

STUB_SUITE: Dict[str, Any] = {
    "suite_title": "离线桩·需求驱动用例套件",
    "cases": [
        {"id": "tc-01", "priority": "P0", "module": "登录", "title": "手机号登录",
         "goal": "使用手机号完成登录", "assert_rule": "进入首页"},
        {"id": "tc-02", "priority": "P1", "module": "搜索", "title": "搜索房源",
         "goal": "搜索小区并查看结果", "assert_rule": "结果列表非空", "depends_on": "tc-01"},
    ],
}


def _fake_synthesize(doc_text: str, filename: str = "", provider: Optional[str] = None,
                     model: Optional[str] = None, **_: Any) -> Dict[str, Any]:
    return {**STUB_SUITE, "cases": [dict(c) for c in STUB_SUITE["cases"]]}


def stub_doc_synthesizer(test: TestCase) -> None:
    """在 setUp 中调用；测试结束自动还原"""
    patcher = patch("core.test_spec_synthesizer.TestSpecSynthesizer.synthesize_from_doc",
                    side_effect=_fake_synthesize)
    patcher.start()
    test.addCleanup(patcher.stop)
