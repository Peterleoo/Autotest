import pytest
from unittest.mock import MagicMock, patch
from ai_engine.screen_parser import ScreenParser, PerceptionMode
from ai_engine.test_agent import AITestAgent

# ==========================================
# 1. 元素树丰富度判定 (is_hierarchy_rich) 测试
# ==========================================

def test_is_hierarchy_rich_standard_native_page():
    """验证标准原生表单页面（包含丰富文本与交互控件）判定为充沛"""
    elements = [
        {"index": 1, "text": "手机号登录", "desc": "", "clickable": False, "is_input": False, "class": "TextView"},
        {"index": 2, "text": "", "desc": "请输入手机号", "clickable": True, "is_input": True, "class": "EditText"},
        {"index": 3, "text": "获取验证码", "desc": "", "clickable": True, "is_input": False, "class": "Button"},
        {"index": 4, "text": "我已阅读并同意用户协议", "desc": "", "clickable": True, "is_input": False, "class": "CheckBox"},
        {"index": 5, "text": "登录", "desc": "", "clickable": True, "is_input": False, "class": "Button"},
    ]
    assert ScreenParser.is_hierarchy_rich(elements) is True


def test_is_hierarchy_rich_sparse_container():
    """验证自绘 Flutter / Webview 容器（仅 1~2 个容器节点无文本）判定为稀疏"""
    elements = [
        {"index": 1, "text": "", "desc": "", "clickable": False, "is_input": False, "class": "FrameLayout"},
        {"index": 2, "text": "", "desc": "", "clickable": True, "is_input": False, "class": "View"},
    ]
    assert ScreenParser.is_hierarchy_rich(elements) is False


def test_is_hierarchy_rich_target_keyword_hit():
    """验证测试目标关键词命中时即使元素较少也能快速判定充沛"""
    elements = [
        {"index": 1, "text": "二手房", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
        {"index": 2, "text": "新房", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
        {"index": 3, "text": "搜索", "desc": "", "clickable": True, "is_input": False, "class": "ImageView"},
    ]
    assert ScreenParser.is_hierarchy_rich(elements, goal="点击二手房进入房源列表") is True


def test_is_hierarchy_rich_excludes_captcha_slider():
    """验证检测到图形滑块或行为验证拼图时一票否决原生短路，必须视觉介入"""
    elements = [
        {"index": 1, "text": "安全验证", "desc": "", "clickable": False, "is_input": False, "class": "TextView"},
        {"index": 2, "text": "拖动下方滑块完成拼图", "desc": "", "clickable": False, "is_input": False, "class": "TextView"},
        {"index": 3, "text": "", "desc": "滑块", "clickable": True, "is_input": False, "class": "ImageView"},
        {"index": 4, "text": "刷新", "desc": "", "clickable": True, "is_input": False, "class": "Button"},
    ]
    assert ScreenParser.is_hierarchy_rich(elements) is False


# ==========================================
# 2. 感知模式评估器 (evaluate_perception_mode) 测试
# ==========================================

def test_evaluate_perception_mode_level1_hierarchy_text():
    """Level 1: 原生 UI 树充沛，模式为 HIERARCHY_TEXT，高置信度"""
    hierarchy = [
        {"index": 1, "text": "首页", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
        {"index": 2, "text": "二手房", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
        {"index": 3, "text": "租房", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
        {"index": 4, "text": "我的", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
    ]
    mode, conf, reason = ScreenParser.evaluate_perception_mode(hierarchy)
    assert mode == PerceptionMode.HIERARCHY_TEXT
    assert conf >= 0.9
    assert "原生 UI 树信息充沛" in reason


def test_evaluate_perception_mode_level2_ocr_text():
    """Level 2: 原生 UI 树稀疏，但端侧本地 OCR 补齐丰富，模式为 OCR_TEXT"""
    hierarchy = [
        {"index": 1, "text": "", "desc": "", "clickable": True, "is_input": False, "class": "ViewGroup"}
    ]
    ocr_elements = [
        {"text": "保利天悦 3室2厅", "center": [300, 400]},
        {"text": "售价 350万", "center": [300, 450]},
        {"text": "咨询经纪人", "center": [800, 450]},
    ]
    mode, conf, reason = ScreenParser.evaluate_perception_mode(hierarchy, ocr_elements=ocr_elements)
    assert mode == PerceptionMode.OCR_TEXT
    assert conf >= 0.8
    assert "端侧本地 OCR 成功补齐" in reason


def test_evaluate_perception_mode_level3_full_vision_sparse():
    """Level 3: 原生与 OCR 均无有效文字（纯图标/自绘图元），兜底升格为 FULL_VISION"""
    hierarchy = [
        {"index": 1, "text": "", "desc": "", "clickable": True, "is_input": False, "class": "ImageView"}
    ]
    ocr_elements = []
    mode, conf, reason = ScreenParser.evaluate_perception_mode(hierarchy, ocr_elements=ocr_elements)
    assert mode == PerceptionMode.FULL_VISION
    assert "启用视觉大模型攻坚" in reason


def test_evaluate_perception_mode_level3_captcha():
    """Level 3: 包含拖动滑块/拼图验证码，升格为 FULL_VISION"""
    hierarchy = [
        {"index": 1, "text": "按住滑块，拖动到最右边", "desc": "", "clickable": False, "is_input": False, "class": "TextView"},
        {"index": 2, "text": "确定", "desc": "", "clickable": True, "is_input": False, "class": "Button"},
    ]
    mode, conf, reason = ScreenParser.evaluate_perception_mode(hierarchy)
    assert mode == PerceptionMode.FULL_VISION
    assert "滑块" in reason


def test_evaluate_perception_mode_forced_vision():
    """强制视觉模式生效（用于异常重试、核验驳回等场景）"""
    hierarchy = [
        {"index": 1, "text": "首页", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
        {"index": 2, "text": "二手房", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
        {"index": 3, "text": "租房", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
        {"index": 4, "text": "我的", "desc": "", "clickable": True, "is_input": False, "class": "TextView"},
    ]
    mode, conf, reason = ScreenParser.evaluate_perception_mode(hierarchy, force_vision=True)
    assert mode == PerceptionMode.FULL_VISION
    assert "强制启用" in reason


# ==========================================
# 3. ScreenParser.get_screen_summary 极速短路测试
# ==========================================

def test_screen_parser_shortcuts_ocr_when_hierarchy_rich():
    """当原生 UI 树充沛时，get_screen_summary 自动跳过端侧 OCR 计算，直接短路"""
    mock_driver = MagicMock()
    mock_driver.get_screenshot_as_base64.return_value = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    mock_driver.page_source = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
        <android.widget.FrameLayout bounds="[0,0][1080,2400]">
            <android.widget.TextView text="应用首页" bounds="[100,100][400,200]" clickable="false" />
            <android.widget.TextView text="二手房" bounds="[100,300][300,400]" clickable="true" />
            <android.widget.TextView text="租房" bounds="[400,300][600,400]" clickable="true" />
            <android.widget.TextView text="我的" bounds="[700,300][900,400]" clickable="true" />
        </android.widget.FrameLayout>
    </hierarchy>
    """

    with patch("core.vision_ocr.VisionOCR.recognize_elements") as mock_ocr:
        res = ScreenParser.get_screen_summary(mock_driver, skip_ocr_if_rich=True)
        # 极速短路：VisionOCR 不会被调用！
        mock_ocr.assert_not_called()
        assert res["perception_mode"] == PerceptionMode.HIERARCHY_TEXT
        assert res["hierarchy_rich"] is True
        assert len(res["elements"]) == 4


# ==========================================
# 4. AITestAgent 分层分流与大模型视觉参数调度测试
# ==========================================

def test_test_agent_dispatches_no_image_for_hierarchy_text():
    """验证当页面为 HIERARCHY_TEXT 时，Agent 调用大模型时不传图片（image_base64=None）"""
    mock_driver = MagicMock()
    mock_driver.get_screenshot_as_base64.return_value = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    mock_driver.page_source = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
        <android.widget.FrameLayout bounds="[0,0][1080,2400]">
            <android.widget.TextView text="应用首页" bounds="[100,100][400,200]" clickable="false" />
            <android.widget.TextView text="二手房" bounds="[100,300][300,400]" clickable="true" />
            <android.widget.TextView text="租房" bounds="[400,300][600,400]" clickable="true" />
            <android.widget.TextView text="我的" bounds="[700,300][900,400]" clickable="true" />
        </android.widget.FrameLayout>
    </hierarchy>
    """

    agent = AITestAgent(driver=mock_driver)
    agent.llm = MagicMock()
    agent.llm.client = MagicMock()
    agent.llm.model_name = "test-model"
    # 让大模型第一步返回 finish 结束测试
    agent.llm.chat_decision.return_value = {
        "thought": "【当前界面判断】：应用首页。已看到目标信息。",
        "action": "finish",
        "reason": "目标已完成"
    }

    with patch("ai_engine.verifier.TaskVerifier.verify_finish_claim", return_value=(True, "验证通过", {})):
        result = agent.run_goal("查看首页二手房推荐", max_steps=1)

    assert result["success"] is True
    # 核心断言：大模型调用时的 image_base64 参数必须为 None！
    call_args = agent.llm.chat_decision.call_args
    assert call_args is not None
    assert call_args.kwargs.get("image_base64") is None


def test_test_agent_dispatches_image_for_full_vision():
    """验证当页面为 FULL_VISION（如自绘/图形滑块）时，Agent 调用大模型必须传原始截屏进行多模态理解"""
    mock_driver = MagicMock()
    b64_mock = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    mock_driver.get_screenshot_as_base64.return_value = b64_mock
    # 纯自绘容器，无文字
    mock_driver.page_source = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
        <android.widget.FrameLayout bounds="[0,0][1080,2400]" />
    </hierarchy>
    """

    agent = AITestAgent(driver=mock_driver)
    agent.llm = MagicMock()
    agent.llm.client = MagicMock()
    agent.llm.model_name = "test-model"
    agent.llm.chat_decision.return_value = {
        "thought": "【当前界面判断】：纯图形界面，点击中心位置。",
        "action": "finish",
        "reason": "已完成"
    }

    with patch("core.vision_ocr.VisionOCR.recognize_elements", return_value=([], False)):
        with patch("ai_engine.verifier.TaskVerifier.verify_finish_claim", return_value=(True, "验证通过", {})):
            result = agent.run_goal("纯图形界面测试", max_steps=1)

    assert result["success"] is True
    call_args = agent.llm.chat_decision.call_args
    assert call_args is not None
    # 核心断言：多模态视觉大模型必须收到 Base64 图片！
    assert call_args.kwargs.get("image_base64") is not None


def test_test_agent_auto_escalation_to_vision_on_action_failure():
    """验证执行动作失败后，下一步自动升格为视觉攻坚（force_vision=True）"""
    mock_driver = MagicMock()
    mock_driver.get_screenshot_as_base64.return_value = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    mock_driver.page_source = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
        <android.widget.FrameLayout bounds="[0,0][1080,2400]">
            <android.widget.TextView text="应用首页" bounds="[100,100][400,200]" clickable="false" />
            <android.widget.TextView text="二手房" bounds="[100,300][300,400]" clickable="true" />
            <android.widget.TextView text="租房" bounds="[400,300][600,400]" clickable="true" />
            <android.widget.TextView text="我的" bounds="[700,300][900,400]" clickable="true" />
        </android.widget.FrameLayout>
    </hierarchy>
    """

    agent = AITestAgent(driver=mock_driver)
    agent.llm = MagicMock()
    agent.llm.client = MagicMock()
    agent.llm.model_name = "test-model"

    # 第一步下发 tap 但执行失败，第二步下发 finish
    agent.llm.chat_decision.side_effect = [
        {
            "thought": "点击不存在的元素",
            "action": "tap",
            "target_index": 999,
            "reason": "测试失败升格"
        },
        {
            "thought": "视觉攻坚完成",
            "action": "finish",
            "reason": "完成测试"
        }
    ]

    with patch("ai_engine.verifier.TaskVerifier.verify_finish_claim", return_value=(True, "验证通过", {})):
        agent.run_goal("测试自适应升格", max_steps=2)

    # 验证两次调用：
    # 第 1 次纯文本（image_base64=None）
    # 第 2 次因第 1 次执行失败，自适应升格为视觉攻坚（image_base64 必须不为 None）
    calls = agent.llm.chat_decision.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs.get("image_base64") is None
    assert calls[1].kwargs.get("image_base64") is not None
