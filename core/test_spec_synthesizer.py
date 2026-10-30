# -*- coding: utf-8 -*-
"""
需求文档驱动测试用例智能提炼引擎 (Test Specification Synthesizer)
遵循 KISS 原则，支持从 DOCX / PDF / MD / TXT 等需求文档中智能提炼强类型系统级测试用例套件 (TestSuite)。
支持 Gemini 3.8 / AntigravityDirectClient / LLMClient 多模型驱动与健壮降级兜底。
"""

import os
import re
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.llm_client import LLMClient
from core.document_extractor import DocumentExtractor

logger = logging.getLogger("TestSpecSynthesizer")


class TestSpecSynthesizer:
    """
    智能用例套件生成与提炼中枢
    """

    SYSTEM_PROMPT = """你是一位资深移动端测试架构师与质量工程专家。
你的任务是从用户提供的软件需求规格说明书 (PRD / 需求文档) 中，提炼出结构严密、可自动化执行的系统级端到端测试用例套件 (Test Suite)。

输出必须为严格合法的 JSON 对象，格式如下：
{
  "suite_title": "基于需求提炼的套件主标题（简练明确）",
  "doc_filename": "文档名",
  "cases": [
    {
      "id": "tc-01",
      "title": "用例标题（如：短信验证码登录与用户协议快速授权）",
      "module": "所属业务模块（如：账号鉴权、核心搜索、业务表单、逆向流程等）",
      "priority": "P0", // 仅限 "P0", "P1", "P2"
      "goal": "端到端执行目标（包含入口导航、点击/滑动/输入等具体交互目标）",
      "assert_rule": "明确的端侧视图或业务断言规则（如：断言页面跳转至首页并展示用户头像）",
      "depends_on": "继承前置状态说明（若前置需已登录则填'继承登录态'，无则填空字符串）"
    }
  ]
}

用例设计要求：
1. 覆盖 3~6 项核心业务主干与边界场景，形成完整端到端闭环；
2. 优先级分配科学：核心业务链路为 P0，主干辅助功能为 P1，边缘与边界巡检为 P2；
3. 状态串联：后续用例若可以在已登录或已进入某些页面现场直接接续执行，在 depends_on 明确标注'继承登录态'或相应前序状态；
4. 严禁输出 Markdown 代码块外的任何多余闲聊，必须返回纯 JSON。
"""

    @classmethod
    def synthesize_from_file(
        cls,
        file_path: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """从本地文件路径中提取文本并提炼用例套件"""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"需求文档未找到: {file_path}")
        text = DocumentExtractor.extract_text(str(p))
        return cls.synthesize_from_doc(text, filename=p.name, provider=provider, model=model)

    @classmethod
    def synthesize_from_doc(
        cls,
        doc_text: str,
        filename: str,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从需求文档纯文本提炼系统测试用例套件
        具备多模型直连、JSON 容错解析与智能启发式兜底保障能力。
        """
        clean_text = (doc_text or "").strip()
        doc_name = filename or "需求说明文档"

        # 若文档内容过少或为空，直接走启发式生成
        if len(clean_text) < 15:
            logger.warning(f"文档 [{doc_name}] 内容较少，启动启发式规则兜底构建用例套件")
            return cls._heuristic_fallback(clean_text, doc_name)

        user_prompt = f"""需求文档文件名: {doc_name}
文档实际内容如下：
---
{clean_text[:6000]}
---
请仔细阅读并根据上述内容提炼出 3~6 项结构化端到端测试用例套件，以纯 JSON 格式输出。"""

        # 尝试调用 LLMClient
        try:
            client = LLMClient(provider=provider, model=model)
            res = client.chat_decision(
                system_prompt=cls.SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
            parsed_suite = cls._normalize_and_validate(res, doc_name)
            if parsed_suite and parsed_suite.get("cases"):
                logger.info(f"✨ 成功通过 AI 模型 [{client.provider}] 提炼出 {len(parsed_suite['cases'])} 项系统测试用例")
                return parsed_suite
        except Exception as e:
            logger.warning(f"调用 AI 模型提炼测试用例异常 ({e})，启用本地智能规则兜底生成: {e}")

        # 降级兜底方案
        return cls._heuristic_fallback(clean_text, doc_name)

    @classmethod
    def _normalize_and_validate(cls, data: Any, doc_name: str) -> Optional[Dict[str, Any]]:
        """清洗、归一化与校验 AI 返回的用例数据"""
        if not isinstance(data, dict):
            return None

        # 尝试兼容包裹层
        suite_obj = data
        if "test_suite" in data and isinstance(data["test_suite"], dict):
            suite_obj = data["test_suite"]
        elif "suite" in data and isinstance(data["suite"], dict):
            suite_obj = data["suite"]

        cases_raw = suite_obj.get("cases") or []
        if not isinstance(cases_raw, list) or len(cases_raw) == 0:
            return None

        normalized_cases = []
        for idx, item in enumerate(cases_raw):
            if not isinstance(item, dict):
                continue
            case_id = item.get("id") or f"tc-{idx+1:02d}"
            title = str(item.get("title") or f"测试用例 {idx+1}").strip()
            module = str(item.get("module") or "业务主流程").strip()
            prio = str(item.get("priority") or "P1").strip().upper()
            if prio not in ["P0", "P1", "P2"]:
                prio = "P1"
            goal = str(item.get("goal") or title).strip()
            assert_rule = str(item.get("assert_rule") or "断言页面状态正常且关键元素可见").strip()
            depends_on = str(item.get("depends_on") or "").strip()

            normalized_cases.append({
                "id": case_id,
                "title": title,
                "module": module,
                "priority": prio,
                "goal": goal,
                "assert_rule": assert_rule,
                "depends_on": depends_on,
                "checked": prio in ["P0", "P1"]
            })

        if not normalized_cases:
            return None

        suite_title = suite_obj.get("suite_title") or f"{Path(doc_name).stem} · 系统级测试套件"

        return {
            "suite_title": suite_title,
            "doc_filename": doc_name,
            "cases": normalized_cases
        }

    @classmethod
    def _heuristic_fallback(cls, doc_text: str, doc_name: str) -> Dict[str, Any]:
        """
        本地启发式语义解析兜底生成引擎
        根据文档关键词与结构段落，推导最具业务合理性的测试用例
        """
        stem = Path(doc_name).stem
        cases: List[Dict[str, Any]] = []

        # 1. 登录鉴权链路探测
        if any(k in doc_text for k in ["登录", "注册", "验证码", "密码", "手机号", "token", "auth", "鉴权"]):
            cases.append({
                "id": "tc-01",
                "title": "验证码/账号安全登录与协议授权",
                "module": "账号鉴权",
                "priority": "P0",
                "goal": "启动目标应用，同意服务隐私协议，输入测试凭据完成鉴权登录进入首页",
                "assert_rule": "断言登录态建立且顺利跳转进入主界面",
                "depends_on": "",
                "checked": True
            })

        # 2. 核心搜索与业务浏览
        if any(k in doc_text for k in ["搜索", "检索", "列表", "筛选", "房源", "商品", "查询", "推荐"]):
            cases.append({
                "id": f"tc-{len(cases)+1:02d}",
                "title": "核心业务频道检索与列表流转加载",
                "module": "核心搜索",
                "priority": "P0",
                "goal": "通过首页顶栏搜索或分类频道输入关键词检索，并在列表页上下滑动加载",
                "assert_rule": "断言列表成功加载并呈现有效业务卡片项",
                "depends_on": "继承登录态" if cases else "",
                "checked": True
            })

        # 3. 业务发布或表单提交
        if any(k in doc_text for k in ["发布", "提交", "委托", "表单", "填写", "预约", "新增", "创建"]):
            cases.append({
                "id": f"tc-{len(cases)+1:02d}",
                "title": "业务核心表单录入与空值校验拦截",
                "module": "业务表单",
                "priority": "P1",
                "goal": "进入业务表单录入页面，测试必填项拦截逻辑与合规数据完整提交",
                "assert_rule": "断言缺失必填项时出现前端提示，完整输入后提交成功",
                "depends_on": "继承登录态" if cases else "",
                "checked": True
            })

        # 4. 详情核验与深度交互
        if any(k in doc_text for k in ["详情", "咨询", "客服", "电话", "收藏", "分享", "评论"]):
            cases.append({
                "id": f"tc-{len(cases)+1:02d}",
                "title": "业务详情页深度交互与功能联动",
                "module": "详情交互",
                "priority": "P1",
                "goal": "点击任一业务列表项进入详情页，体验图文轮播、微聊咨询或功能收藏",
                "assert_rule": "断言详情要素完整加载，操作交互触发即时响应",
                "depends_on": "继承登录态" if cases else "",
                "checked": True
            })

        # 5. 个人中心与边界巡检
        cases.append({
            "id": f"tc-{len(cases)+1:02d}",
            "title": "主导航快速切换与页面鲁棒性巡检",
            "module": "边界巡检",
            "priority": "P2",
            "goal": "在底栏主要 Tab 之间交替切换，检查网络重连与视图渲染鲁棒性",
            "assert_rule": "断言界面无黑白屏或崩溃报错，导航栏状态正确定位",
            "depends_on": "",
            "checked": False
        })

        # 兜底补充确保至少 3 个
        while len(cases) < 3:
            if not any(c.get("module") == "主干流程" for c in cases):
                cases.insert(0, {
                    "id": "tc-00",
                    "title": f"{stem} 核心主干流程巡检",
                    "module": "主干流程",
                    "priority": "P0",
                    "goal": "启动应用，完成关键路径导航浏览与核心功能可用性验证",
                    "assert_rule": "断言首屏加载正常且核心交互链路通畅",
                    "depends_on": "",
                    "checked": True
                })
            elif not any(c.get("module") == "核心业务" for c in cases):
                cases.insert(1, {
                    "id": "tc-01",
                    "title": f"{stem} 核心业务交互校验",
                    "module": "核心业务",
                    "priority": "P1",
                    "goal": "浏览主屏核心业务内容，触发基础交互与列表滑动",
                    "assert_rule": "断言界面数据渲染完备，交互响应及时",
                    "depends_on": "继承前序状态",
                    "checked": True
                })
            else:
                cases.append({
                    "id": "tc-02",
                    "title": f"{stem} 边界鲁棒性探索",
                    "module": "边界巡检",
                    "priority": "P2",
                    "goal": "快速切换功能频道，验证异常抗扰能力",
                    "assert_rule": "断言无白屏崩溃报错",
                    "depends_on": "",
                    "checked": False
                })

        # 重排 id
        for idx, c in enumerate(cases):
            c["id"] = f"tc-{idx+1:02d}"

        return {
            "suite_title": f"基于【{stem}】提炼的系统级测试用例套件",
            "doc_filename": doc_name,
            "cases": cases
        }
