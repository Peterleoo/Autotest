import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger("Solidifier")

ROBUST_HELPERS_CODE = '''
def robust_click(driver, text=None, res_id=None, desc=None, rel_x=None, rel_y=None):
    """
    双模自适应点击 (Dual-Mode Click)
    模式 1: 优先语义匹配 (文本/ID/无障碍描述)
    模式 2: 分辨率相对百分比动态换算兜底
    """
    if text:
        try:
            el = driver.find_element(AppiumBy.XPATH, f"//*[@text='{text}' or contains(@text, '{text}')]")
            el.click()
            return
        except Exception:
            pass
    if res_id:
        try:
            el = driver.find_element(AppiumBy.ID, res_id)
            el.click()
            return
        except Exception:
            pass
    if desc:
        try:
            el = driver.find_element(AppiumBy.ACCESSIBILITY_ID, desc)
            el.click()
            return
        except Exception:
            pass

    # 兜底：相对百分比换算实际物理坐标
    if rel_x is not None and rel_y is not None:
        size = driver.get_window_size()
        w = size.get('width', 1080)
        h = size.get('height', 2160)
        target_x = int(w * rel_x)
        target_y = int(h * rel_y)
        if hasattr(driver, "tap"):
            driver.tap([(target_x, target_y)])
        else:
            driver.execute_adb(["shell", "input", "tap", str(target_x), str(target_y)])
        return

    raise RuntimeError(f"无法定位或点击目标元素: text={text}, id={res_id}, rel=({rel_x}, {rel_y})")


def robust_type(driver, text=None, res_id=None, desc=None, rel_x=None, rel_y=None, input_text=""):
    """
    双模自适应输入 (Dual-Mode Type)
    优先语义查找输入框，相对坐标点击聚焦兜底并注入文本
    """
    typed = False
    if text or res_id or desc:
        try:
            el = None
            if res_id:
                try: el = driver.find_element(AppiumBy.ID, res_id)
                except Exception: pass
            if not el and text:
                try: el = driver.find_element(AppiumBy.XPATH, f"//*[@text='{text}' or contains(@text, '{text}')]")
                except Exception: pass
            if not el and desc:
                try: el = driver.find_element(AppiumBy.ACCESSIBILITY_ID, desc)
                except Exception: pass
            if el:
                el.clear()
                el.send_keys(input_text)
                typed = True
                return
        except Exception:
            pass

    if not typed:
        robust_click(driver, text=text, res_id=res_id, desc=desc, rel_x=rel_x, rel_y=rel_y)
        time.sleep(0.3)
        try:
            driver.switch_to.active_element.send_keys(input_text)
        except Exception:
            if hasattr(driver, "execute_adb"):
                driver.execute_adb(["shell", "input", "text", input_text])


def robust_swipe(driver, direction="up", repeat=1):
    """自适应屏幕物理分辨率滑动"""
    size = driver.get_window_size()
    w = size.get('width', 1080)
    h = size.get('height', 2160)
    for _ in range(repeat):
        if direction == "up":
            driver.swipe(w // 2, int(h * 0.75), w // 2, int(h * 0.25), 450)
        elif direction == "down":
            driver.swipe(w // 2, int(h * 0.25), w // 2, int(h * 0.75), 450)
        elif direction == "left":
            driver.swipe(int(w * 0.88), h // 2, int(w * 0.12), h // 2, 350)
        elif direction == "right":
            driver.swipe(int(w * 0.12), h // 2, int(w * 0.88), h // 2, 350)
        time.sleep(0.3)
'''


class Solidifier:
    """
    测试脚本固化生成器 (Dual-Mode Resilient Solidification):
    将 AI 探索和执行测试生成的动态轨迹（Action Trace）
    编译为标准的、跨分辨率自适应的 Pytest + Appium + Requests 原生测试脚本。
    
    核心架构优势：
    1. 语义优先模式 (Semantic First): 优先匹配唯一文本、resource-id 或 accessibility-id，100% 免疫不同尺寸设备布局微移；
    2. 相对分辨率百分比兜底 (Responsive Coordinate Fallback): 自动将像素转换为浮点相对比例 (0.0~1.0)，任何设备动态适配；
    3. 免 AI 高频回归: 一次 AI 探索录制，沉淀为标准原生脚本，可在 CI/CD 中毫秒级并发执行。
    """

    @staticmethod
    def solidify_test_case(
        case_name: str,
        goal: str,
        action_history: List[Dict[str, Any]],
        output_dir: Optional[Path] = None
    ) -> Path:
        out_dir = output_dir or settings.SOLIDIFIED_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        # 规范化文件名与方法名
        clean_name = re.sub(r"[^\w]+", "_", case_name).strip("_").lower()
        if not clean_name.startswith("test_"):
            clean_name = f"test_{clean_name}"

        file_path = out_dir / f"{clean_name}.py"
        logger.info(f"正在将 AI 测试轨迹固化为双模自适应脚本: {file_path}")

        steps_code = []
        for i, step in enumerate(action_history, 1):
            action = step.get("action")
            reason = step.get("reason", f"Step {i}")
            loc = step.get("locator", {}) or {}

            # 提取语义属性
            t_text = step.get("element_text") or loc.get("text") or (loc.get("value") if loc.get("by") == "xpath" and "@text=" in str(loc.get("value")) else None)
            t_id = step.get("element_id") or loc.get("res_id") or (loc.get("value") if loc.get("by") == "id" else None)
            t_desc = step.get("element_desc") or loc.get("desc") or (loc.get("value") if loc.get("by") == "accessibility_id" else None)

            # 提取坐标与计算相对百分比
            rel_x, rel_y = None, None
            center = step.get("center")
            coord_val = loc.get("value") if loc.get("by") == "coordinates" else None
            if not center and coord_val and "," in str(coord_val):
                try:
                    parts = str(coord_val).split(",")
                    center = [int(parts[0]), int(parts[1])]
                except Exception:
                    pass

            win_size = step.get("screen_size") or {"width": 1080, "height": 2160}
            w_base = win_size.get("width", 1080)
            h_base = win_size.get("height", 2160)

            if center and len(center) == 2:
                rel_x = round(center[0] / max(1, w_base), 4)
                rel_y = round(center[1] / max(1, h_base), 4)

            if action == "tap":
                text_arg = f"text={repr(t_text)}" if t_text else "text=None"
                id_arg = f"res_id={repr(t_id)}" if t_id else "res_id=None"
                desc_arg = f"desc={repr(t_desc)}" if t_desc else "desc=None"
                rx_arg = f"rel_x={rel_x}" if rel_x is not None else "rel_x=None"
                ry_arg = f"rel_y={rel_y}" if rel_y is not None else "rel_y=None"

                steps_code.append(
                    f"    # 步骤 {i}: {reason}\n"
                    f"    robust_click(driver, {text_arg}, {id_arg}, {desc_arg}, {rx_arg}, {ry_arg})\n"
                    f"    time.sleep(1)"
                )

            elif action == "type":
                input_val = step.get("text", "")
                text_arg = f"text={repr(t_text)}" if t_text else "text=None"
                id_arg = f"res_id={repr(t_id)}" if t_id else "res_id=None"
                desc_arg = f"desc={repr(t_desc)}" if t_desc else "desc=None"
                rx_arg = f"rel_x={rel_x}" if rel_x is not None else "rel_x=None"
                ry_arg = f"rel_y={rel_y}" if rel_y is not None else "rel_y=None"

                steps_code.append(
                    f"    # 步骤 {i}: {reason} (输入: {input_val})\n"
                    f"    robust_type(driver, {text_arg}, {id_arg}, {desc_arg}, {rx_arg}, {ry_arg}, input_text={repr(input_val)})\n"
                    f"    time.sleep(1)"
                )

            elif action == "swipe":
                direction = step.get("direction", "up").lower()
                repeat = max(1, int(step.get("repeat", 1)))
                steps_code.append(
                    f"    # 步骤 {i}: 动态自适应滑动 [{direction}] ({repeat} 次)\n"
                    f"    robust_swipe(driver, direction='{direction}', repeat={repeat})\n"
                    f"    time.sleep(1)"
                )

            elif action in ["fast_forward_guide", "skip_guide"]:
                steps_code.append(
                    f"    # 步骤 {i}: 引导页极速穿透宏动作（快速翻页至末页直达主界面）\n"
                    f"    robust_swipe(driver, direction='left', repeat=3)\n"
                    f"    time.sleep(0.5)\n"
                    f"    # 点击标准底部体验按钮区域 (水平居中，垂直75%)\n"
                    f"    robust_click(driver, text='立即体验', rel_x=0.5, rel_y=0.75)\n"
                    f"    time.sleep(1)"
                )

            elif action == "press_key":
                key = step.get("key", "back").lower()
                if key == "back":
                    steps_code.append(f"    # 步骤 {i}: 模拟返回键\n    driver.back()\n    time.sleep(1)")

            elif action == "wait":
                secs = step.get("seconds", 2)
                steps_code.append(f"    # 步骤 {i}: 等待界面加载\n    time.sleep({secs})")

            elif action == "assert_text":
                expected = step.get("expected", "")
                steps_code.append(
                    f"    # 步骤 {i}: 校验界面是否包含预期内容 [{expected}]\n"
                    f"    assert '{expected}' in driver.page_source, f'业务断言失败：界面未出现预期内容 [{expected}]'"
                )

            elif action == "call_api":
                method = step.get("method", "GET")
                endpoint = step.get("endpoint", "")
                req_json = step.get("json")
                status = step.get("expected_status", 200)
                json_str = f", json={req_json}" if req_json else ""
                steps_code.append(
                    f"    # 步骤 {i}: 接口测试 [{method} {endpoint}]\n"
                    f"    resp = api_client.request('{method}', '{endpoint}'{json_str})\n"
                    f"    assert resp.status_code == {status}, f'接口状态码断言失败: {{resp.status_code}} != {status}'"
                )

        formatted_steps = "\n\n".join(steps_code) if steps_code else "    pass"

        template = f'''"""
由 AI 自动化测试智能体自动录制固化的跨端测试用例 (Dual-Mode Resilient Test Suite)
测试目标: {goal}
执行命令: pytest {file_path.name} -v -s
特性优势:
  1. 语义优先 (Text / ID / Desc) 动态查找；
  2. 屏幕自适应百分比相对坐标兜底，免维护跨不同分辨率真机回归！
"""
import time
import pytest
import allure
from appium.webdriver.common.appiumby import AppiumBy

from core.driver_factory import DriverFactory
from core.api_client import APIClient

{ROBUST_HELPERS_CODE}

@pytest.fixture(scope="module")
def driver():
    """初始化真机驱动"""
    drv = DriverFactory.create_driver()
    yield drv
    drv.quit()


@pytest.fixture(scope="module")
def api_client():
    """初始化统一接口客户端"""
    return APIClient()


@allure.feature("固化测试套件")
@allure.story("{goal}")
def {clean_name}(driver, api_client):
    """
    自动化用例: {clean_name}
    测试目标: {goal}
    """
{formatted_steps}
'''
        file_path.write_text(template, encoding="utf-8")
        logger.info(f"✅ 跨端双模固化脚本生成成功: {file_path.name}")

        try:
            from core.deliverables_manager import deliverables_mgr
            rel_path = f"tests/solidified/{file_path.name}"
            deliverables_mgr.register_test_script(
                script_relative_path=rel_path,
                title=f"{clean_name}: {goal[:32]}",
                case_id=clean_name
            )
        except Exception as ex:
            logger.warning(f"注册交付物至 .pm/deliverables.json 失败: {ex}")

        return file_path
