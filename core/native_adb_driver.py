import base64
import re
import subprocess
import time
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict, Any
from config.settings import settings

logger = logging.getLogger("NativeADBDriver")

class NativeElement:
    """模拟 Appium WebElement 的原生 ADB 元素轻量实现"""
    def __init__(self, driver: "NativeADBDriver", bounds: str = "", text: str = "", res_id: str = ""):
        self.driver = driver
        self.bounds = bounds
        self.text = text
        self.center_x, self.center_y = None, None

        if bounds:
            match = re.findall(r"\[(\d+),(\d+)\]", bounds)
            if len(match) == 2:
                x1, y1 = map(int, match[0])
                x2, y2 = map(int, match[1])
                self.center_x = (x1 + x2) // 2
                self.center_y = (y1 + y2) // 2

    def click(self):
        if self.center_x is None or self.center_y is None:
            raise ValueError(f"元素无有效物理坐标，无法执行点击: {self.text or self.res_id}")
        logger.info(f"原生 ADB 点击坐标: ({self.center_x}, {self.center_y}) [元素: {self.text or self.res_id}]")
        self.driver.execute_adb(["shell", "input", "tap", str(self.center_x), str(self.center_y)])
        time.sleep(0.6)

    def send_keys(self, text: str):
        self.click()
        time.sleep(0.3)
        logger.info(f"原生 ADB 输入文本: '{text}'")
        self.driver.execute_adb(["shell", "input", "text", text])

    def clear(self):
        self.click()
        time.sleep(0.2)
        # 连按 20 次退格键清除已有文本
        for _ in range(20):
            self.driver.execute_adb(["shell", "input", "keyevent", "67"])


class NativeADBDriver:
    """
    原生 ADB 极速真机驱动引擎（Pure ADB Native Driver）
    核心价值：
    1. 彻底跳过 Appium 必须注入 helper/androidTest APK 的弊病；
    2. 100% 免疫华为/小米/OPPO/VIVO 等国内机型的【应用未备案/风险拦截】弹窗；
    3. 秒级启动待测应用，实时抓取 1080P 高保真原机截图并解析原生 UI 控件树；
    4. 完全无缝兼容现有 AITestAgent、ScreenParser 与 ActionExecutor。
    """
    def __init__(self, device_id: Optional[str] = None):
        from core.app_manager import AppManager
        self.adb_bin = AppManager().adb_bin
        self.device_id = device_id
        self._detect_device()

    def _detect_device(self):
        if not self.device_id:
            res = subprocess.run([self.adb_bin, "devices"], capture_output=True, text=True, timeout=5)
            for line in res.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    self.device_id = parts[0]
                    break
        if not self.device_id:
            raise ConnectionError("未检测到在线的 Android 真机或模拟器！")

    def execute_adb(self, cmd_args: List[str], timeout: int = 15) -> subprocess.CompletedProcess:
        full_cmd = [self.adb_bin]
        if self.device_id:
            full_cmd.extend(["-s", self.device_id])
        full_cmd.extend(cmd_args)
        return subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)

    @property
    def page_source(self) -> str:
        """通过原生 uiautomator dump 提取当前屏幕控件树 XML（无需安装任何 APK）"""
        try:
            self.execute_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], timeout=10)
            res = self.execute_adb(["shell", "cat", "/sdcard/window_dump.xml"], timeout=10)
            xml_text = res.stdout.strip()
            if xml_text.startswith("<?xml") or "<hierarchy" in xml_text:
                return xml_text
        except Exception as e:
            logger.warning(f"获取原生 UI 树失败: {e}")
        return "<hierarchy></hierarchy>"

    def get_screenshot_as_base64(self) -> str:
        """截取真机物理屏幕，返回 base64 字符串（极速高保真）"""
        raw_bytes = self.get_screenshot_as_png()
        return base64.b64encode(raw_bytes).decode("utf-8")

    def get_screenshot_as_png(self) -> bytes:
        """通过 adb exec-out screencap 获取物理屏幕原图二进制字节"""
        full_cmd = [self.adb_bin]
        if self.device_id:
            full_cmd.extend(["-s", self.device_id])
        full_cmd.extend(["exec-out", "screencap", "-p"])
        res = subprocess.run(full_cmd, capture_output=True, timeout=10)
        return res.stdout

    def find_element(self, by: Any, value: str) -> NativeElement:
        """从页面中定位元素并包装为 NativeElement"""
        by_str = str(by).lower()
        source = self.page_source
        try:
            root = ET.fromstring(source.encode("utf-8"))
            for node in root.iter():
                attrib = node.attrib
                b = attrib.get("bounds", "")
                t = attrib.get("text", "")
                r = attrib.get("resource-id", "")
                d = attrib.get("content-desc", "")

                if "xpath" in by_str:
                    # 匹配 text 或 resource-id
                    m_t = re.search(r"@text='([^']+)'", value)
                    m_r = re.search(r"@resource-id='([^']+)'", value)
                    if m_t and m_t.group(1) == t:
                        return NativeElement(self, b, t, r)
                    if m_r and m_r.group(1) in r:
                        return NativeElement(self, b, t, r)
                    if t and t in value:
                        return NativeElement(self, b, t, r)
                elif "id" in by_str:
                    if r == value or value in r:
                        return NativeElement(self, b, t, r)
                elif "accessibility" in by_str:
                    if d == value:
                        return NativeElement(self, b, t, r)
                elif "text" in by_str:
                    if t == value:
                        return NativeElement(self, b, t, r)
        except Exception as e:
            logger.warning(f"元素查找解析异常: {e}")

        raise ValueError(f"在当前页面未找到匹配元素 (by={by}, value={value})")

    def back(self):
        """模拟物理返回键"""
        logger.info("原生 ADB 模拟按返回键")
        self.execute_adb(["shell", "input", "keyevent", "4"])

    def launch_app(self, package: str, activity: str):
        """直接调起真机目标应用前台，零重装零弹窗"""
        logger.info(f"原生 ADB 秒级调起应用: {package}/{activity}")
        self.execute_adb(["shell", "am", "start", "-n", f"{package}/{activity}"])
        time.sleep(1.5)

    def implicitly_wait(self, timeout: int):
        pass

    def quit(self):
        logger.info("原生 ADB 会话结束")
