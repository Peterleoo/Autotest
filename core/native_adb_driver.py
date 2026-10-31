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
        try:
            res = subprocess.run([self.adb_bin, "devices"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            lines = res.stdout.strip().split("\n")[1:]
        except Exception as e:
            raise ConnectionError(f"无法执行 ADB 获取设备列表: {e}")

        online_devices = []
        abnormal_devices = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                dev_id, status = parts[0], parts[1]
                if status == "device":
                    online_devices.append(dev_id)
                else:
                    abnormal_devices[dev_id] = status

        if self.device_id:
            if self.device_id in online_devices:
                return
            status = abnormal_devices.get(self.device_id)
            if status == "offline":
                try:
                    logger.warning(f"设备 [{self.device_id}] 处于 offline 状态，尝试执行 adb reconnect...")
                    subprocess.run([self.adb_bin, "reconnect", "offline"], capture_output=True, timeout=5)
                    time.sleep(1)
                    res = subprocess.run([self.adb_bin, "devices"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
                    for l in res.stdout.strip().split("\n")[1:]:
                        p = l.split()
                        if len(p) >= 2 and p[0] == self.device_id and p[1] == "device":
                            logger.info(f"设备 [{self.device_id}] 自动重连成功！")
                            return
                except Exception:
                    pass
                raise ConnectionError(f"目标真机 [{self.device_id}] 处于离线状态 (offline)。请重新插拔 USB 数据线或重启手机开发者选项中的【USB 调试】。")
            elif status == "unauthorized":
                raise ConnectionError(f"目标真机 [{self.device_id}] 未获得 USB 调试授权 (unauthorized)。请点亮手机屏幕并在弹出授权提示框中勾选【始终允许这台电脑调试】。")
            else:
                raise ConnectionError(f"目标真机 [{self.device_id}] 未连接或无法识别 (当前状态: {status or '未找到'})。请检查 USB 连接。")
        else:
            if online_devices:
                self.device_id = online_devices[0]
            else:
                if abnormal_devices:
                    dev_id, st = next(iter(abnormal_devices.items()))
                    raise ConnectionError(f"检测到设备 [{dev_id}] 但处于异常状态 [{st}]，无法激活驱动。请检查手机 USB 调试连接与授权。")
                raise ConnectionError("未检测到任何已连接的物理真机！杜绝免机仿真，请使用 USB 数据线连接真机并启用 USB 调试。")

        # 🚀 毫秒级手势注入权限健康探针（有记录直接用，无记录 AI 自动分析）
        try:
            from core.device_knowledge_manager import device_knowledge_mgr
            ok, tip = device_knowledge_mgr.probe_input_permission(self.device_id)
            if not ok:
                dev_fp = device_knowledge_mgr.get_device_fingerprint(self.device_id)
                err_msg = f"真机手势模拟点击权限未就绪：{tip}"
                logger.error(f"❌ 【{dev_fp.get('brand')} {dev_fp.get('model')}】{err_msg}")
                raise PermissionError(f"【{dev_fp.get('brand')} {dev_fp.get('model')}】{err_msg}")
        except PermissionError:
            raise
        except Exception as e:
            logger.warning(f"跳过手势探针校验: {e}")

        # ⚡ 自动唤醒屏幕并启用 USB 供电常亮保护 (Device Health Watchdog)
        self.ensure_device_awake()

    def ensure_device_awake(self):
        """
        Device Health Watchdog (设备常态保活哨兵)
        1. 探活并自动唤醒屏幕 (input keyevent 224)
        2. 启用 USB 连接常亮保护 (svc power stayon usb)
        3. 轻量上滑解开无密码滑动锁屏，保证界面随时处于可交互状态
        """
        if not self.device_id:
            return
        try:
            res = subprocess.run([self.adb_bin, "-s", self.device_id, "shell", "dumpsys", "power"], capture_output=True, text=True, timeout=4)
            out = res.stdout or ""
            is_off = ("mHoldingDisplaySuspendBlocker=false" in out) or ("Display Power: state=OFF" in out) or ("isInteractive=false" in out)
            if is_off:
                logger.info(f"⚡ [Device Watchdog] 设备 [{self.device_id}] 处于熄屏状态，立即下发唤醒指令...")
                subprocess.run([self.adb_bin, "-s", self.device_id, "shell", "input", "keyevent", "224"], capture_output=True, timeout=3)
                time.sleep(0.3)
                # 上滑解开普通滑动锁
                subprocess.run([self.adb_bin, "-s", self.device_id, "shell", "input", "swipe", "540", "1800", "540", "600", "250"], capture_output=True, timeout=3)
            # 固化 USB 供电常亮保护，防止测试中意外黑屏休眠
            subprocess.run([self.adb_bin, "-s", self.device_id, "shell", "svc", "power", "stayon", "usb"], capture_output=True, timeout=3)
        except Exception as e:
            logger.debug(f"保活探针跳过: {e}")

    def execute_adb(self, cmd_args: List[str], timeout: int = 15) -> subprocess.CompletedProcess:
        full_cmd = [self.adb_bin]
        if self.device_id:
            full_cmd.extend(["-s", self.device_id])
        full_cmd.extend(cmd_args)
        try:
            res = subprocess.run(
                full_cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout
            )
            err = (res.stderr or "").lower()
            if "device offline" in err or "device not found" in err:
                logger.warning(f"⚠️ [Watchdog 掉线自愈] 设备 [{self.device_id}] 临时离线，尝试执行快速重连...")
                subprocess.run([self.adb_bin, "reconnect", "offline"], capture_output=True, timeout=4)
                time.sleep(0.8)
                res = subprocess.run(
                    full_cmd, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=timeout
                )
            return res
        except subprocess.TimeoutExpired:
            logger.error(f"ADB 指令超时: {' '.join(full_cmd)}")
            raise

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
        """
        获取真机物理分辨率原图，供 OCR 与 AI 视觉使用。
        注意：实时投屏的 480 宽缩略图会丢失自绘/Flutter 页面的文字细节与坐标精度，
        因此这里优先走全分辨率 screencap，失败后再回退到投屏帧。
        """
        full_cmd = [self.adb_bin]
        if self.device_id:
            full_cmd.extend(["-s", self.device_id])
        full_cmd.extend(["exec-out", "screencap", "-p"])
        try:
            res = subprocess.run(full_cmd, capture_output=True, timeout=10)
            raw = res.stdout
            if res.returncode == 0 and raw:
                if not raw.startswith(b"\x89PNG\x0d\x0a\x1a\x0a") and b"PNG" in raw[:16]:
                    raw = raw.replace(b"\r\r\n", b"\n").replace(b"\r\n", b"\n")
                if raw.startswith(b"\x89PNG"):
                    return raw
        except Exception as e:
            logger.warning(f"全分辨率截图失败，回退投屏帧: {e}")

        try:
            from core.screen_stream_hub import _capture_raw_and_encode_sync, HAS_OPENCV
            import cv2
            target_dev = self.device_id
            if not target_dev:
                self._detect_device()
                target_dev = self.device_id
            frame_data = _capture_raw_and_encode_sync(self.adb_bin, target_dev)
            if frame_data:
                bgr = frame_data.get("bgr")
                if HAS_OPENCV and bgr is not None:
                    _, buf = cv2.imencode('.png', bgr)
                    return buf.tobytes()
                elif frame_data.get("jpeg"):
                    return frame_data["jpeg"]
        except Exception:
            pass

        return b""

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

    def is_app_foreground(self, package: str) -> bool:
        """精准检测目标包是否真正处于当前屏幕前台焦点"""
        if not package:
            return False
        try:
            res_focus = self.execute_adb(["shell", "dumpsys", "window"])
            for line in res_focus.stdout.splitlines():
                if ("mCurrentFocus" in line or "mFocusedApp" in line) and f"{package}/" in line:
                    return True
        except Exception:
            pass
        return False

    def launch_app(self, package: str, activity: Optional[str] = None):
        """直接调起真机目标应用前台，零重装零弹窗（支持前台智能就地接管）"""
        self.ensure_device_awake()
        if not package:
            return

        if self.is_app_foreground(package):
            logger.info(f"⚡ [就地接管] 目标应用 [{package}] 真正处于前台活跃状态，保留当前页面现场，无需重复冷启动！")
            return

        # 若未指定 activity，尝试极速解析主启动 Activity
        if not activity:
            try:
                res_act = self.execute_adb(["shell", "cmd", "package", "resolve-activity", "--brief", package])
                for line in res_act.stdout.splitlines():
                    if "/" in line and package in line:
                        activity = line.strip().split("/", 1)[1]
                        break
            except Exception:
                pass

        if activity:
            act_target = activity if "/" in activity else f"{package}/{activity}"
            logger.info(f"原生 ADB 秒级调起应用: {act_target}")
            res = self.execute_adb(["shell", "am", "start", "-n", act_target])
            output = (res.stdout + " " + res.stderr).strip()
            if "Error" in output or "does not exist" in output or "not found" in output:
                logger.warning(f"am start 调起应用异常: {output}，尝试降级 monkey 唤起...")
                self.execute_adb(["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])
        else:
            logger.info(f"原生 ADB Monkey 唤起应用: {package}")
            self.execute_adb(["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])

        time.sleep(1.5)

    def get_window_size(self) -> Dict[str, int]:
        """获取真机物理屏幕分辨率 (width, height)"""
        try:
            res = self.execute_adb(["shell", "wm", "size"])
            m = re.search(r"(\d+)x(\d+)", res.stdout)
            if m:
                return {"width": int(m.group(1)), "height": int(m.group(2))}
        except Exception:
            pass
        return {"width": 1080, "height": 2160}

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 500):
        """执行原生平滑微步滑动"""
        self.execute_adb(["shell", "input", "swipe", str(int(start_x)), str(int(start_y)), str(int(end_x)), str(int(end_y)), str(int(duration))])
        time.sleep(0.5)

    def implicitly_wait(self, timeout: int):
        pass

    def tap(self, positions: List[Any], duration: Optional[int] = None):
        """兼容 Appium 标准 driver.tap([(x, y)]) 物理坐标点击"""
        if not positions:
            return
        pos = positions[0]
        if isinstance(pos, (tuple, list)) and len(pos) >= 2:
            x, y = int(pos[0]), int(pos[1])
        else:
            return
        logger.info(f"原生 ADB 物理触控点击: ({x}, {y})")
        if duration and duration > 100:
            self.execute_adb(["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration)])
        else:
            self.execute_adb(["shell", "input", "tap", str(x), str(y)])
        time.sleep(0.5)

    def get_current_app(self) -> str:
        """获取当前前台应用包名/窗口名"""
        try:
            res = self.execute_adb(["shell", "dumpsys", "window"])
            for line in res.stdout.splitlines():
                if "mCurrentFocus" in line or "mFocusedApp" in line:
                    return line.strip()
        except Exception:
            pass
        return ""

    def execute_shell(self, command: str) -> str:
        """执行原生 adb shell 指令"""
        cmd_args = ["shell"] + command.split()
        res = self.execute_adb(cmd_args)
        return (res.stdout or res.stderr or "").strip()

    def quit(self):
        logger.info("原生 ADB 会话结束")
