import time
import logging
from typing import Dict, Any, List, Optional
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput

from core.api_client import APIClient

logger = logging.getLogger("ActionExecutor")

class ActionExecutor:
    """
    负责执行 AI 规划的各种原子操作，并记录详细轨迹（用于后续一键固化）
    """
    def __init__(self, driver: webdriver.Remote, api_client: Optional[APIClient] = None, app_identifier: Optional[str] = None):
        self.driver = driver
        self.api_client = api_client or APIClient()
        self.app_identifier = app_identifier
        self.action_history: List[Dict[str, Any]] = []

    def execute(self, action_dict: Dict[str, Any], elements_map: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行一条动作字典，例如：
        {"action": "tap", "target_index": 3, "reason": "点击登录按钮"}
        {"action": "type", "target_index": 2, "text": "testuser", "reason": "输入账号"}
        {"action": "call_api", "method": "POST", "endpoint": "/login", "json": {...}}
        {"action": "assert_text", "expected": "欢迎回来", "reason": "断言登录成功"}
        """
        action = action_dict.get("action", "").lower()
        reason = action_dict.get("reason", "")
        logger.info(f"==> 执行动作 [{action}]: {reason}")

        result = {"success": True, "message": ""}
        trace_item = {"action": action, "reason": reason, "raw_dict": action_dict}
        t_action_start = time.perf_counter()

        try:
            if action == "tap":
                target_idx = action_dict.get("target_index")
                el_info = self._find_element_by_index(target_idx, elements_map)
                locator = self._locate_and_click(el_info, action_dict.get("coordinates"))
                trace_item["locator"] = locator
                if el_info:
                    trace_item["element_text"] = el_info.get("text", "")
                    trace_item["element_desc"] = el_info.get("desc", "")
                    trace_item["element_id"] = el_info.get("resource_id", "")
                    trace_item["center"] = el_info.get("center")
                win_size = getattr(self.driver, "get_window_size", lambda: {"width": 1080, "height": 2160})()
                trace_item["screen_size"] = win_size

            elif action == "type":
                target_idx = action_dict.get("target_index")
                raw_text = action_dict.get("text", "")
                el_info = self._find_element_by_index(target_idx, elements_map)
                
                # 接入 SmartFormFiller 智能推断引擎 (支持优先使用真实应用预置凭证)
                from ai_engine.form_filler import SmartFormFiller
                text = SmartFormFiller.infer_value(el_info, raw_text=raw_text, app_identifier=self.app_identifier)
                
                locator = self._locate_and_type(el_info, text)
                trace_item["locator"] = locator
                trace_item["text"] = text
                if el_info:
                    trace_item["element_text"] = el_info.get("text", "")
                    trace_item["element_desc"] = el_info.get("desc", "")
                    trace_item["element_id"] = el_info.get("resource_id", "")
                    trace_item["center"] = el_info.get("center")
                win_size = getattr(self.driver, "get_window_size", lambda: {"width": 1080, "height": 2160})()
                trace_item["screen_size"] = win_size

            elif action == "swipe":
                direction = action_dict.get("direction", "up").lower()
                repeat = max(1, int(action_dict.get("repeat", 1)))
                for i in range(repeat):
                    self._swipe(direction)
                    if i < repeat - 1:
                        time.sleep(0.35)
                trace_item["direction"] = direction
                trace_item["repeat"] = repeat

            elif action in ["fast_forward_guide", "skip_guide"]:
                # 引导页极速穿透宏动作：一气呵成连滑 3 次直达末页并点击体验/进入
                logger.info("⚡ 执行【引导页极速穿透宏动作】：快速连翻 3 页直达末页...")
                for _ in range(3):
                    self._swipe("left")
                    time.sleep(0.3)
                time.sleep(0.6)
                # 尝试点击进入按钮（优先点击 OCR 识别到的‘马上体验/立即体验/跳过/进入’，若未提取则盲按标准底部按钮区域）
                clicked = False
                for el in elements_map:
                    txt = el.get("text", "")
                    if any(kw in txt for kw in ["马上体验", "立即体验", "立即进入", "开始体验", "跳过", "进入首页", "随便看看"]):
                        self._locate_and_click(el, None)
                        clicked = True
                        break
                if not clicked:
                    # 黄金标准体验按钮区域：屏幕水平居中偏下位置
                    win_size = getattr(self.driver, "get_window_size", lambda: {"width": 1080, "height": 2160})()
                    btn_x = win_size.get("width", 1080) // 2
                    btn_y = int(win_size.get("height", 2160) * 0.75)
                    logger.info(f"点击引导页标准体验按钮区: ({btn_x}, {btn_y})")
                    if hasattr(self.driver, "execute_adb"):
                        self.driver.execute_adb(["shell", "input", "tap", str(btn_x), str(btn_y)])
                trace_item["macro"] = "fast_forward_guide"

            elif action == "press_key":
                key = action_dict.get("key", "back").lower()
                if key == "back":
                    self.driver.back()
                trace_item["key"] = key

            elif action == "wait":
                seconds = action_dict.get("seconds", 2)
                time.sleep(seconds)
                trace_item["seconds"] = seconds

            elif action == "assert_text":
                expected = action_dict.get("expected", "")
                page_source = self.driver.page_source
                if expected not in page_source:
                    raise AssertionError(f"页面未包含预期文本: '{expected}'")
                logger.info(f"断言成功：页面包含预期文本 '{expected}'")
                trace_item["expected"] = expected

            elif action == "call_api":
                method = action_dict.get("method", "GET")
                endpoint = action_dict.get("endpoint", "")
                req_json = action_dict.get("json")
                expected_code = action_dict.get("expected_status", 200)

                resp = self.api_client.request(method, endpoint, json=req_json)
                if resp.status_code != expected_code:
                    raise AssertionError(f"接口 {endpoint} 预期状态码 {expected_code}，实际返回 {resp.status_code}")
                
                trace_item["method"] = method
                trace_item["endpoint"] = endpoint
                trace_item["json"] = req_json
                trace_item["expected_status"] = expected_code
                result["api_response"] = resp.text[:500]

            elif action == "finish":
                logger.info("AI 判定测试目标已达成！")
                trace_item["status"] = "FINISHED"

            else:
                raise ValueError(f"未知动作类型: {action}")

            cost_ms = int((time.perf_counter() - t_action_start) * 1000)
            cost_str = f"{cost_ms}ms" if cost_ms < 1000 else f"{round(cost_ms / 1000, 2)}s"
            result["cost_time"] = cost_str
            result["duration_ms"] = cost_ms
            trace_item["cost_time"] = cost_str
            trace_item["duration_ms"] = cost_ms

            self.action_history.append(trace_item)
            time.sleep(1.0) # 短暂等待页面渲染
            return result

        except Exception as e:
            cost_ms = int((time.perf_counter() - t_action_start) * 1000)
            cost_str = f"{cost_ms}ms" if cost_ms < 1000 else f"{round(cost_ms / 1000, 2)}s"
            logger.error(f"执行动作 [{action}] 失败: {e}")
            result["success"] = False
            result["message"] = str(e)
            result["cost_time"] = cost_str
            result["duration_ms"] = cost_ms
            trace_item["error"] = str(e)
            trace_item["cost_time"] = cost_str
            trace_item["duration_ms"] = cost_ms
            self.action_history.append(trace_item)
            return result

    def _find_element_by_index(self, index: Optional[int], elements_map: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if index is None:
            return None
        for el in elements_map:
            if el["index"] == index:
                return el
        return None

    def _locate_and_click(self, el_info: Optional[Dict[str, Any]], coordinates: Optional[List[int]]) -> Dict[str, str]:
        """优先使用精确物理坐标直接点击；若为 Appium 驱动且无坐标则查找元素"""
        point = coordinates or (el_info["center"] if el_info and el_info.get("center") else None)

        # 1. 优先使用 NativeADBDriver 原生物理坐标点击（最稳定、零延迟，免疫一切 Hybrid / 自绘框架无控件树问题）
        if point and hasattr(self.driver, "execute_adb"):
            x, y = point
            name = el_info.get("text") or el_info.get("desc") or "目标位置" if el_info else "坐标"
            t0 = time.perf_counter()
            self.driver.execute_adb(["shell", "input", "tap", str(x), str(y)])
            cost_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(f"原生 ADB 物理手势精准点击完成: ({x}, {y}) [{name}] (用时 {cost_ms}ms)")
            return {
                "by": "coordinates",
                "value": f"{x},{y}",
                "cost_ms": cost_ms,
                "text": el_info.get("text", "") if el_info else "",
                "res_id": el_info.get("resource_id", "") if el_info else "",
                "desc": el_info.get("desc", "") if el_info else ""
            }

        # 2. 如果是传统 Appium 驱动且元素有定位符
        if el_info:
            if el_info.get("resource_id"):
                by = AppiumBy.ID
                val = el_info["resource_id"]
                self.driver.find_element(by, val).click()
                return {"by": "id", "value": val}
            elif el_info.get("desc"):
                by = AppiumBy.ACCESSIBILITY_ID
                val = el_info["desc"]
                self.driver.find_element(by, val).click()
                return {"by": "accessibility_id", "value": val}
            elif el_info.get("text"):
                xpath = f"//*[@text='{el_info['text']}']"
                self.driver.find_element(AppiumBy.XPATH, xpath).click()
                return {"by": "xpath", "value": xpath}

        # 3. Fallback Appium W3C 坐标点击
        if point:
            x, y = point
            actions = ActionChains(self.driver)
            actions.w3c_actions = ActionBuilder(self.driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
            actions.w3c_actions.pointer_action.move_to_location(x, y)
            actions.w3c_actions.pointer_action.pointer_down()
            actions.w3c_actions.pointer_action.pause(0.1)
            actions.w3c_actions.pointer_action.pointer_up()
            actions.perform()
            return {"by": "coordinates", "value": f"{x},{y}"}

        raise ValueError("无法定位目标点击元素（无有效定位符且无坐标）")

    def _locate_and_type(self, el_info: Optional[Dict[str, Any]], text: str) -> Dict[str, str]:
        """定位输入框并填入文字"""
        if not el_info:
            raise ValueError("输入目标元素信息为空")

        # 优先支持原生 ADB 坐标点击输入
        if el_info.get("center") and hasattr(self.driver, "execute_adb"):
            self._locate_and_click(el_info, None)
            time.sleep(0.5)

            # 判断是否包含中文汉字
            if any(ord(c) > 127 for c in text):
                try:
                    import base64
                    import re

                    def _encode_imap_utf7(s: str) -> str:
                        def _chunk(c: str) -> str:
                            b = c.encode("utf-16be")
                            return base64.b64encode(b).decode("ascii").rstrip("=").replace("/", ",")
                        parts = re.split(r"([^\x20-\x7e]+)", s)
                        res = []
                        for p in parts:
                            if not p: continue
                            if all(0x20 <= ord(ch) <= 0x7e for ch in p):
                                res.append(p.replace("&", "&-"))
                            else:
                                res.append(f"&{_chunk(p)}-")
                        return "".join(res)

                    # 激活免权限 UnicodeIME 输入法（真机已就绪）
                    self.driver.execute_adb(["shell", "ime", "enable", "io.appium.settings/.UnicodeIME"])
                    self.driver.execute_adb(["shell", "ime", "set", "io.appium.settings/.UnicodeIME"])
                    utf7_encoded = _encode_imap_utf7(text)
                    logger.info(f"原生 ADB UnicodeIME 中文汉字极速上屏: '{text}' (RFC3501: {utf7_encoded})")
                    # 使用单引号包裹，防止 Android /system/bin/sh 将 & 误判为后台任务
                    self.driver.execute_adb(["shell", "input", "text", f"'{utf7_encoded}'"])
                except Exception as e:
                    logger.warning(f"UnicodeIME 输入汉字异常，回退拼音: {e}")
                    from pypinyin import lazy_pinyin
                    pinyin_str = "".join(lazy_pinyin(text)[:2])
                    self.driver.execute_adb(["shell", "input", "text", pinyin_str])
            else:
                logger.info(f"原生 ADB 直接输入文本: '{text}'")
                self.driver.execute_adb(["shell", "input", "text", text])

            time.sleep(0.5)
            return {"by": "coordinates", "value": str(el_info["center"])}

        element = None
        locator = {}
        if el_info.get("resource_id"):
            locator = {"by": "id", "value": el_info["resource_id"]}
            element = self.driver.find_element(AppiumBy.ID, el_info["resource_id"])
        elif el_info.get("desc"):
            locator = {"by": "accessibility_id", "value": el_info["desc"]}
            element = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, el_info["desc"])
        elif el_info.get("text"):
            xpath = f"//*[@text='{el_info['text']}']"
            locator = {"by": "xpath", "value": xpath}
            element = self.driver.find_element(AppiumBy.XPATH, xpath)
        elif el_info.get("center"):
            self._locate_and_click(el_info, None)
            time.sleep(0.5)
            # 通过当前焦点元素输入
            element = self.driver.switch_to.active_element
            locator = {"by": "active_element", "value": ""}

        if element:
            element.clear()
            element.send_keys(text)
            return locator
        raise ValueError("未找到可输入的文本框")

    def _swipe(self, direction: str):
        """通用滑动手势（采用平滑温和微步长，杜绝大跨度甩动与视口越界死锁）"""
        if hasattr(self.driver, "execute_adb"):
            logger.info(f"原生 ADB 执行平滑微步滑动手势: {direction}")
            if direction == "up":
                # 从屏幕中下部温和平缓滑至中上部 (跨度 400px，时长 600ms，无猛甩惯性)
                self.driver.execute_adb(["shell", "input", "swipe", "540", "1350", "540", "950", "600"])
            elif direction == "down":
                self.driver.execute_adb(["shell", "input", "swipe", "540", "950", "540", "1350", "600"])
            elif direction == "left":
                # 水平翻页手势：采用快速跨屏滑动 (跨度 830px，时长 300ms)，确保顺利触发 ViewPager 翻页
                self.driver.execute_adb(["shell", "input", "swipe", "950", "1000", "120", "1000", "300"])
            elif direction == "right":
                self.driver.execute_adb(["shell", "input", "swipe", "120", "1000", "950", "1000", "300"])
            return

        size = self.driver.get_window_size()
        width = size["width"]
        height = size["height"]

        if direction == "up": # 向上滑，屏幕内容往上滚，跨度取 20% 高度
            start_x, start_y = width // 2, int(height * 0.65)
            end_x, end_y = width // 2, int(height * 0.45)
        elif direction == "down":
            start_x, start_y = width // 2, int(height * 0.45)
            end_x, end_y = width // 2, int(height * 0.65)
        elif direction == "left":
            start_x, start_y = int(width * 0.7), height // 2
            end_x, end_y = int(width * 0.3), height // 2
        else: # right
            start_x, start_y = int(width * 0.3), height // 2
            end_x, end_y = int(width * 0.7), height // 2

        self.driver.swipe(start_x, start_y, end_x, end_y, duration=600)
