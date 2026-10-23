import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger("Solidifier")

class Solidifier:
    """
    测试脚本固化生成器：
    将 AI 探索和执行测试生成的动态轨迹（Action Trace）
    编译/固化为标准的、确定性的 Pytest + Appium + Requests 原生测试脚本。
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
        logger.info(f"正在将 AI 测试轨迹固化为自动化脚本: {file_path}")

        # 生成 Pytest 代码段
        steps_code = []
        for i, step in enumerate(action_history, 1):
            action = step.get("action")
            reason = step.get("reason", f"Step {i}")

            if action == "tap":
                loc = step.get("locator", {})
                by = loc.get("by")
                val = loc.get("value")
                if by == "id":
                    steps_code.append(f"    # 步骤 {i}: {reason}\n    driver.find_element(AppiumBy.ID, '{val}').click()\n    time.sleep(1)")
                elif by == "accessibility_id":
                    steps_code.append(f"    # 步骤 {i}: {reason}\n    driver.find_element(AppiumBy.ACCESSIBILITY_ID, '{val}').click()\n    time.sleep(1)")
                elif by == "xpath":
                    steps_code.append(f"    # 步骤 {i}: {reason}\n    driver.find_element(AppiumBy.XPATH, \"{val}\").click()\n    time.sleep(1)")
                elif by == "coordinates":
                    x, y = map(int, val.split(","))
                    steps_code.append(f"    # 步骤 {i}: {reason} (坐标点击)\n    driver.tap([({x}, {y})])\n    time.sleep(1)")

            elif action == "type":
                loc = step.get("locator", {})
                by = loc.get("by")
                val = loc.get("value")
                text = step.get("text", "")
                if by == "id":
                    steps_code.append(f"    # 步骤 {i}: {reason}\n    el = driver.find_element(AppiumBy.ID, '{val}')\n    el.clear()\n    el.send_keys('{text}')\n    time.sleep(0.5)")
                elif by == "accessibility_id":
                    steps_code.append(f"    # 步骤 {i}: {reason}\n    el = driver.find_element(AppiumBy.ACCESSIBILITY_ID, '{val}')\n    el.clear()\n    el.send_keys('{text}')\n    time.sleep(0.5)")
                elif by == "xpath":
                    steps_code.append(f"    # 步骤 {i}: {reason}\n    el = driver.find_element(AppiumBy.XPATH, \"{val}\")\n    el.clear()\n    el.send_keys('{text}')\n    time.sleep(0.5)")
                else:
                    steps_code.append(f"    # 步骤 {i}: {reason}\n    el = driver.switch_to.active_element\n    el.send_keys('{text}')\n    time.sleep(0.5)")

            elif action == "swipe":
                direction = step.get("direction", "up")
                repeat = step.get("repeat", 1)
                if repeat > 1:
                    if direction == "left":
                        steps_code.append(
                            f"    # 步骤 {i}: 连续向左快速翻页 {repeat} 次\n"
                            f"    size = driver.get_window_size()\n"
                            f"    w, h = size['width'], size['height']\n"
                            f"    for _ in range({repeat}):\n"
                            f"        driver.swipe(int(w * 0.88), h // 2, int(w * 0.12), h // 2, 300)\n"
                            f"        time.sleep(0.35)\n"
                            f"    time.sleep(1)"
                        )
                    else:
                        steps_code.append(
                            f"    # 步骤 {i}: 连续滑动手势 [{direction}] ({repeat} 次)\n"
                            f"    size = driver.get_window_size()\n"
                            f"    for _ in range({repeat}):\n"
                            f"        driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 500)\n"
                            f"        time.sleep(0.35)\n"
                            f"    time.sleep(1)"
                        )
                else:
                    if direction == "left":
                        steps_code.append(
                            f"    # 步骤 {i}: 滑动手势 [left]\n"
                            f"    size = driver.get_window_size()\n"
                            f"    w, h = size['width'], size['height']\n"
                            f"    driver.swipe(int(w * 0.88), h // 2, int(w * 0.12), h // 2, 300)\n"
                            f"    time.sleep(1)"
                        )
                    else:
                        steps_code.append(
                            f"    # 步骤 {i}: 滑动手势 [{direction}]\n"
                            f"    size = driver.get_window_size()\n"
                            f"    driver.swipe(size['width']//2, int(size['height']*0.7), size['width']//2, int(size['height']*0.3), 500)\n"
                            f"    time.sleep(1)"
                        )

            elif action in ["fast_forward_guide", "skip_guide"]:
                steps_code.append(
                    f"    # 步骤 {i}: 引导页极速穿透宏动作（快速翻页至末页并进入首页）\n"
                    f"    size = driver.get_window_size()\n"
                    f"    w, h = size['width'], size['height']\n"
                    f"    for _ in range(3):\n"
                    f"        driver.swipe(int(w * 0.88), h // 2, int(w * 0.12), h // 2, 300)\n"
                    f"        time.sleep(0.3)\n"
                    f"    time.sleep(0.5)\n"
                    f"    driver.tap([(w // 2, int(h * 0.75))])\n"
                    f"    time.sleep(1)"
                )

            elif action == "press_key":
                key = step.get("key", "back")
                if key == "back":
                    steps_code.append(f"    # 步骤 {i}: 模拟返回键\n    driver.back()\n    time.sleep(1)")

            elif action == "wait":
                secs = step.get("seconds", 2)
                steps_code.append(f"    # 步骤 {i}: 等待界面加载\n    time.sleep({secs})")

            elif action == "assert_text":
                expected = step.get("expected", "")
                steps_code.append(f"    # 步骤 {i}: 断言页面包含文本 [{expected}]\n    assert '{expected}' in driver.page_source, f'断言失败：页面未出现预期文本: {expected}'")

            elif action == "call_api":
                method = step.get("method", "GET")
                endpoint = step.get("endpoint", "")
                req_json = step.get("json")
                status = step.get("expected_status", 200)
                json_str = f", json={req_json}" if req_json else ""
                steps_code.append(f"    # 步骤 {i}: 接口测试 [{method} {endpoint}]\n    resp = api_client.request('{method}', '{endpoint}'{json_str})\n    assert resp.status_code == {status}, f'接口状态码断言失败: {{resp.status_code}} != {status}'")

        formatted_steps = "\n\n".join(steps_code) if steps_code else "    pass"

        # 模板组合
        template = f'''"""
由 AI 自动化测试智能体自动固化生成的测试用例
测试目标: {goal}
生成时间: 自动化录制后生成
执行方式: pytest {file_path.name} -v -s
"""
import time
import pytest
import allure
from appium.webdriver.common.appiumby import AppiumBy

from core.driver_factory import DriverFactory
from core.api_client import APIClient

@pytest.fixture(scope="module")
def driver():
    """初始化 Appium 驱动"""
    drv = DriverFactory.create_driver()
    yield drv
    drv.quit()

@pytest.fixture(scope="module")
def api_client():
    """初始化统一接口客户端"""
    return APIClient()

@allure.feature("固化测试套件")
@allure.story("{goal}")
def test_{clean_name}(driver, api_client):
    """
    自动化用例: {clean_name}
    {goal}
    """
{formatted_steps}
'''
        file_path.write_text(template, encoding="utf-8")
        logger.info(f"✅ 固化脚本生成成功: {file_path.name}")
        
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
