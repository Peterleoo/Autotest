# -*- coding: utf-8 -*-
"""
需求驱动用例智能生成与自由编排套件 (Suite Builder) 自动化单元与集成测试
覆盖：
1. 文档纯文本提取 -> 结构化用例套件生成 (LLM + 语义规则兜底)
2. 用例套件增删改调序与优先级/状态依赖校验
3. 测试套件本地持久化存盘与加载
4. 系统级串联执行 (run_systemic_suite) 与状态现场继承 (keep_state)
5. FastAPI HTTP 端点集成验证 (/api/test_suite/*)
"""

import os
import json
import time
import asyncio
import unittest
from pathlib import Path

from core.test_spec_synthesizer import TestSpecSynthesizer
from core.task_manager import TaskManager, TEST_SUITES_STORE_DIR
from web.app import (
    synthesize_test_suite,
    run_systemic_test_suite,
    save_test_suite_endpoint,
    list_test_suites_endpoint,
)

ROOT = Path(__file__).resolve().parent.parent


class TestTestSpecSynthesizer(unittest.TestCase):

    def setUp(self):
        self.mgr = TaskManager()
        self.test_suite_ids = []

    def tearDown(self):
        # 清理测试生成的套件文件
        for sid in self.test_suite_ids:
            p = TEST_SUITES_STORE_DIR / f"{sid}.json"
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_01_synthesize_from_doc_structure_and_types(self):
        """测试 1: 文档文本提取 -> 用例套件强类型结构化生成"""
        doc_content = """
        # 房产交易平台核心业务需求说明书 (PRD_v3.2)
        
        ## 1. 账号鉴权
        用户启动应用后，必须阅读并勾选服务与隐私政策协议。支持手机短信验证码登录，若未注册则自动注册。登录成功后返回首页并建立登录态 Token。
        
        ## 2. 核心搜索与列表浏览
        首页顶部常驻全局搜索框。用户输入"精装两居"或商圈名称可触发联想检索。搜索结果列表支持下拉刷新与上拉滑动加载下一页。
        
        ## 3. 房源发布与表单校验
        支持业主与经纪人在线发布房源。发布时售价、小区名称、户型为必填项。若售价为空点击提交，界面须即时红字拦截提示"请输入期望售价"。
        
        ## 4. 异常巡检与逆向流
        在弱网或快速频繁切换底栏首页、找房、消息、我的等各 Tab 时，界面不得出现白屏或崩溃。
        """

        suite = TestSpecSynthesizer.synthesize_from_doc(
            doc_text=doc_content,
            filename="PRD_v3.2.docx"
        )

        self.assertIsInstance(suite, dict)
        self.assertIn("suite_title", suite)
        self.assertIn("doc_filename", suite)
        self.assertEqual(suite["doc_filename"], "PRD_v3.2.docx")
        self.assertIn("cases", suite)
        self.assertGreaterEqual(len(suite["cases"]), 3)

        # 检查每个用例必须包含的标准字段与优先级规范
        for c in suite["cases"]:
            self.assertIn("id", c)
            self.assertIn("title", c)
            self.assertIn("module", c)
            self.assertIn("priority", c)
            self.assertIn(c["priority"], ["P0", "P1", "P2"])
            self.assertIn("goal", c)
            self.assertIn("assert_rule", c)
            self.assertIn("depends_on", c)
            self.assertIn("checked", c)

    def test_02_synthesize_fallback_on_empty_doc(self):
        """测试 2: 极简或空白文档的启发式容错兜底提炼能力"""
        suite = TestSpecSynthesizer.synthesize_from_doc(
            doc_text="",
            filename="空白文档.md"
        )
        self.assertIsInstance(suite, dict)
        self.assertIn("cases", suite)
        self.assertGreaterEqual(len(suite["cases"]), 3)
        # 首项应为可用用例
        first_case = suite["cases"][0]
        self.assertEqual(first_case["priority"], "P0")
        self.assertTrue(first_case["checked"])

    def test_03_normalize_and_validate(self):
        """测试 3: 格式清洗与数据防御性校验"""
        raw_bad_data = {
            "suite_title": "测试套件",
            "cases": [
                {"id": "c1", "title": "用例1", "priority": "invalid_prio", "goal": "目标1"},
                {"title": "用例2", "priority": "P2"}
            ]
        }
        res = TestSpecSynthesizer._normalize_and_validate(raw_bad_data, "test.docx")
        self.assertIsNotNone(res)
        self.assertEqual(len(res["cases"]), 2)
        # 非法优先级应归一化为 P1
        self.assertEqual(res["cases"][0]["priority"], "P1")
        # 缺失 id 应自动补充
        self.assertEqual(res["cases"][1]["id"], "tc-02")
        self.assertEqual(res["cases"][1]["priority"], "P2")

    def test_04_save_and_list_test_suite(self):
        """测试 4: 套件持久化存储 (data/test_suites/) 与列表检索"""
        suite_data = {
            "suite_title": "自动化回归用例套件-CI专用",
            "doc_filename": "CI_Spec.md",
            "keep_state": True,
            "cases": [
                {
                    "id": "tc-01",
                    "title": "短信登录",
                    "module": "账号",
                    "priority": "P0",
                    "goal": "完成短信验证码登录",
                    "assert_rule": "跳转到首页",
                    "depends_on": "",
                    "checked": True
                },
                {
                    "id": "tc-02",
                    "title": "二手房检索",
                    "module": "搜索",
                    "priority": "P0",
                    "goal": "搜索精装房",
                    "assert_rule": "列表有数据",
                    "depends_on": "继承登录态",
                    "checked": True
                }
            ]
        }

        saved = self.mgr.save_test_suite(suite_data)
        suite_id = saved.get("suite_id")
        self.assertIsNotNone(suite_id)
        self.test_suite_ids.append(suite_id)

        # 验证文件落盘
        saved_file = TEST_SUITES_STORE_DIR / f"{suite_id}.json"
        self.assertTrue(saved_file.exists())

        # 读取验证
        loaded = self.mgr.get_test_suite(suite_id)
        self.assertEqual(loaded["suite_title"], "自动化回归用例套件-CI专用")
        self.assertEqual(len(loaded["cases"]), 2)

        # 列表验证
        suites_list = self.mgr.list_test_suites()
        found = any(s.get("suite_id") == suite_id for s in suites_list)
        self.assertTrue(found)

    def test_05_run_systemic_suite_with_keep_state(self):
        """测试 5: 系统级串联执行 (run_systemic_suite) 与状态继承调度"""
        suite_data = {
            "suite_title": "多用例串联系统测试",
            "device_ids": ["mock_device_suite"],
            "cases": [
                {
                    "id": "tc-01",
                    "title": "用例1-登录授权",
                    "module": "鉴权",
                    "priority": "P0",
                    "goal": "执行登录",
                    "assert_rule": "登录成功",
                    "depends_on": "",
                    "checked": True
                },
                {
                    "id": "tc-02",
                    "title": "用例2-房源搜索",
                    "module": "搜索",
                    "priority": "P0",
                    "goal": "搜索二手房",
                    "assert_rule": "返回房源",
                    "depends_on": "继承登录态",
                    "checked": True
                }
            ]
        }

        res = self.mgr.run_systemic_suite(
            session_id=None,
            suite_data=suite_data,
            keep_state=True
        )

        self.assertTrue(res.get("success"))
        session_id = res.get("session_id")
        self.assertIsNotNone(session_id)
        self.assertEqual(res.get("cases_count"), 2)

        # 等待后台执行完成
        max_wait = 10
        sess = None
        for _ in range(max_wait * 5):
            sess = self.mgr.get_session(session_id)
            if sess and sess.get("status") in ["READY_FOR_REVIEW", "COMPLETED", "FAILED"]:
                break
            time.sleep(0.2)

        self.assertIsNotNone(sess)
        self.assertEqual(sess["status"], "READY_FOR_REVIEW")
        self.assertTrue(sess.get("is_success"))
        # 验证步骤包含 2 个串联用例步骤
        plan_steps = sess.get("plan_steps", [])
        self.assertEqual(len(plan_steps), 2)
        for s in plan_steps:
            self.assertEqual(s.get("status"), "COMPLETED")

    def test_06_fastapi_endpoints_direct(self):
        """测试 6: FastAPI HTTP 接口逻辑全链路端到端集成验证"""
        # 1. 提炼接口 POST /api/test_suite/synthesize
        syn_data = asyncio.run(synthesize_test_suite({
            "doc_text": "这是一个测试系统的用户手册，包含登录与查看订单两个功能模块。",
            "filename": "用户手册.txt"
        }))
        self.assertTrue(syn_data["success"])
        self.assertIn("suite", syn_data)
        suite = syn_data["suite"]

        # 2. 保存套件接口 POST /api/test_suite/save
        save_data = asyncio.run(save_test_suite_endpoint(payload={"suite_data": suite}))
        self.assertTrue(save_data["success"])
        saved_id = save_data["suite_id"]
        self.test_suite_ids.append(saved_id)

        # 3. 获取套件列表 GET /api/test_suites
        list_data = asyncio.run(list_test_suites_endpoint())
        self.assertTrue(list_data["success"])
        self.assertGreaterEqual(list_data["total"], 1)

        # 4. 执行套件接口 POST /api/test_suite/run
        suite["device_ids"] = ["mock_fastapi_dev"]
        run_data = asyncio.run(run_systemic_test_suite(payload={
            "suite_data": suite,
            "keep_state": True
        }))
        self.assertTrue(run_data["success"])
        self.assertIn("session_id", run_data)

    def test_07_normalize_robustness_markdown_and_list(self):
        """测试 7: 校验多形态容错解析 (Markdown代码块包裹、纯数组输入与别名字段)"""
        # 1. 模拟 LLM 返回 Markdown 代码块包裹的纯文本 JSON
        markdown_json = """```json
        {
            "suite_title": "房源核心交易测试套件",
            "test_cases": [
                {
                    "title": "业主委托放盘",
                    "module": "房源发布",
                    "priority": "P0",
                    "goal": "进入委托发布页面填写房源信息",
                    "assert_rule": "提交后列表出现对应委托记录",
                    "depends_on": ""
                }
            ]
        }
        ```"""
        parsed = TestSpecSynthesizer._normalize_and_validate(markdown_json, "PRD.docx")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["suite_title"], "房源核心交易测试套件")
        self.assertEqual(len(parsed["cases"]), 1)
        self.assertEqual(parsed["cases"][0]["assert_rule"], "提交后列表出现对应委托记录")

        # 2. 模拟 LLM 直接返回纯数组
        raw_list = [
            {"title": "快速搜索", "priority": "P1", "goal": "输入关键词并回车", "assert_rule": "返回有效结果"}
        ]
        parsed_list = TestSpecSynthesizer._normalize_and_validate(raw_list, "SearchSpec.md")
        self.assertIsNotNone(parsed_list)
        self.assertEqual(len(parsed_list["cases"]), 1)
        self.assertEqual(parsed_list["cases"][0]["title"], "快速搜索")

    def test_08_run_systemic_suite_on_existing_session(self):
        """测试 8: 在已有激活会话中继续执行系统级测试套件 (Session Reuse & State Reset)"""
        # 先创建一个普通会话
        session_id = "test_sess_reuse_001"
        self.mgr.sessions[session_id] = {
            "session_id": session_id,
            "title": "先前单次测试",
            "status": "COMPLETED",
            "plan_steps": [{"step_id": 1, "title": "旧单步任务", "status": "COMPLETED"}],
            "devices": {
                "mock_device_reuse": {
                    "device_id": "mock_device_reuse",
                    "model": "Mock Device",
                    "platform": "Android",
                    "status": "PASS",
                    "step": 5,
                    "max_steps": 5,
                    "logs": ["已完成先前测试"]
                }
            },
            "timeline_blocks": [],
            "turns": []
        }

        suite_data = {
            "suite_title": "在已有会话追加执行套件",
            "cases": [
                {"id": "tc-01", "title": "追加用例1", "priority": "P0", "goal": "用例1", "assert_rule": "断言1"},
                {"id": "tc-02", "title": "追加用例2", "priority": "P1", "goal": "用例2", "assert_rule": "断言2"}
            ]
        }

        res = self.mgr.run_systemic_suite(
            session_id=session_id,
            suite_data=suite_data,
            keep_state=True
        )
        self.assertTrue(res["success"])
        sess = self.mgr.get_session(session_id)
        # 会话状态应重置为 RUNNING，且步骤应更新为 2 个新用例步骤
        self.assertEqual(sess["status"], "RUNNING")
        self.assertEqual(len(sess["plan_steps"]), 2)
        self.assertTrue(sess.get("is_systemic_suite"))
        self.assertEqual(sess["devices"]["mock_device_reuse"]["status"], "RUNNING")

        # 等待后台执行完成
        for _ in range(50):
            sess = self.mgr.get_session(session_id)
            if sess and sess.get("status") in ["READY_FOR_REVIEW", "COMPLETED"]:
                break
            time.sleep(0.1)
        self.assertEqual(sess["status"], "READY_FOR_REVIEW")
        self.assertTrue(sess.get("is_success"))

    def test_09_synthesize_endpoint_with_doc_filename(self):
        """测试 9: 验证 POST /api/test_suite/synthesize 支持 doc_filename 保持用户可读标题"""
        data = asyncio.run(synthesize_test_suite({
            "doc_text": "这是一个测试系统的需求文档，包含注册与充值流程。",
            "filename": "up_1030_173000_1a2b_PRD.docx",
            "doc_filename": "业务需求规格说明书_v2.0.docx"
        }))
        self.assertTrue(data["success"])
        suite = data["suite"]
        # 文档名与标题均严禁泄露内部时间戳随机前缀
        self.assertEqual(suite["doc_filename"], "业务需求规格说明书_v2.0.docx")
        self.assertNotIn("up_1030", suite["suite_title"])
        self.assertNotIn("up_1030", suite["doc_filename"])

        # 验证极简兜底模式下准确使用 doc_filename 作为套件标题
        fallback_data = asyncio.run(synthesize_test_suite({
            "doc_text": "",
            "filename": "up_1030_fallback.docx",
            "doc_filename": "核心资产管理说明书.docx"
        }))
        self.assertTrue(fallback_data["success"])
        self.assertIn("核心资产管理说明书", fallback_data["suite"]["suite_title"])
        self.assertEqual(fallback_data["suite"]["doc_filename"], "核心资产管理说明书.docx")


if __name__ == "__main__":
    unittest.main()
