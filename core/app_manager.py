import os
import re
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict
from config.settings import settings

logger = logging.getLogger("AppManager")

class AppManager:
    """
    负责应用的生命周期管理：安装、卸载、清理、提取包信息
    """
    def __init__(self, platform: Optional[str] = None):
        self.platform = (platform or settings.PLATFORM).lower()
        self.apps_dir = settings.APPS_DIR
        self.adb_bin = self._find_adb()

    def _find_adb(self) -> str:
        """解析 adb 路径，优先环境变量，其次检查 SDK 常见路径"""
        import shutil
        adb_in_path = shutil.which("adb")
        if adb_in_path:
            return adb_in_path
        
        home = Path.home()
        sdk_env = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
        sdk_root = Path(sdk_env) if sdk_env and Path(sdk_env).exists() else (home / "AppData/Local/Android/Sdk")
        fallback = sdk_root / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        if fallback.exists():
            return str(fallback)
        return "adb"

    def get_apk_info(self, apk_path: Path) -> Dict[str, str]:
        """使用 aapt 提取 APK 包名、版本与启动 Activity"""
        info = {"package": "", "activity": "", "label": "", "version": "", "path": str(apk_path)}
        home = Path.home()
        sdk_env = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
        sdk_root = Path(sdk_env) if sdk_env and Path(sdk_env).exists() else (home / "AppData/Local/Android/Sdk")
        aapt_in_path = shutil.which("aapt")
        if aapt_in_path:
            aapt_path = Path(aapt_in_path)
        else:
            found = list((sdk_root / "build-tools").glob("*/aapt*"))
            aapt_path = found[0] if found else (sdk_root / "build-tools" / "36.1.0" / ("aapt.exe" if os.name == "nt" else "aapt"))

        if aapt_path.exists() and apk_path.exists():
            try:
                res = subprocess.run([str(aapt_path), "dump", "badging", str(apk_path)], capture_output=True, text=True, encoding="utf-8", errors="ignore")
                for line in res.stdout.split("\n"):
                    if line.startswith("package:"):
                        m_pkg = re.search(r"name='([^']+)'", line)
                        m_ver = re.search(r"versionName='([^']+)'", line)
                        if m_pkg: info["package"] = m_pkg.group(1)
                        if m_ver: info["version"] = m_ver.group(1)
                    elif "application-label:" in line:
                        m_lbl = re.search(r"application-label:'([^']+)'", line)
                        if m_lbl: info["label"] = m_lbl.group(1)
                    elif "launchable-activity:" in line:
                        m_act = re.search(r"name='([^']+)'", line)
                        if m_act: info["activity"] = m_act.group(1)
            except Exception as e:
                logger.warning(f"aapt 解析失败: {e}")
        return info

    def find_target_app(self, app_name: Optional[str] = None) -> Optional[Path]:
        """从 apps 目录定位安装包"""
        if app_name:
            target = self.apps_dir / app_name
            if target.exists():
                return target

        ext = ".apk" if self.platform == "android" else ".ipa"
        found = list(self.apps_dir.glob(f"*{ext}"))
        if found:
            logger.info(f"自动发现待测安装包: {found[0].name}")
            return found[0]
        logger.warning(f"在 {self.apps_dir} 目录下未找到 {ext} 安装包")
        return None

    def is_app_installed(self, package_name: str, device_id: Optional[str] = None) -> bool:
        """检查手机上是否已经安装了指定包名的应用（使用 0.1s 极速精准的 pm path）"""
        if not package_name or self.platform != "android":
            return False
        try:
            cmd = [self.adb_bin]
            if device_id and device_id not in ["mock-device", "local-simulator", "default"]:
                cmd.extend(["-s", device_id])
            cmd.extend(["shell", "pm", "path", package_name])
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            is_ins = "package:" in res.stdout
            logger.info(f"检查应用 [{package_name}] 在设备 [{device_id or 'default'}] 安装状态: {'已安装' if is_ins else '未安装'}")
            return is_ins
        except Exception as e:
            logger.warning(f"检查包安装状态异常: {e}")
            return False

    def install_android_app(self, apk_path: Path, grant_permissions: bool = True, device_id: Optional[str] = None) -> bool:
        """通过 adb 安装 Android APK，-r 覆盖安装，-g 授予所有运行时权限"""
        if not apk_path.exists():
            logger.error(f"APK 文件不存在: {apk_path}")
            return False

        logger.info(f"开始安装 Android APK: {apk_path.name} ...")
        cmd = [self.adb_bin]
        if device_id and device_id not in ["mock-device", "local-simulator", "default"]:
            cmd.extend(["-s", device_id])
        cmd.extend(["install", "-r"])
        if grant_permissions:
            cmd.append("-g")
        cmd.append(str(apk_path))

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if "Success" in res.stdout:
                logger.info(f"APK 安装成功: {apk_path.name}")
                return True

            err_out = (res.stdout + " " + res.stderr).strip()
            # 若报权限安全异常 (如小米 MIUI 拦截 -g)，降级为普通 install -r
            if grant_permissions and ("INSTALL_GRANT_RUNTIME_PERMISSIONS" in err_out or "SecurityException" in err_out):
                logger.info(f"检测到 -g 权限拦截，降级为纯覆盖安装 (install -r)...")
                cmd_retry = [c for c in cmd if c != "-g"]
                res2 = subprocess.run(cmd_retry, capture_output=True, text=True, timeout=120)
                if "Success" in res2.stdout:
                    logger.info(f"APK 降级安装成功: {apk_path.name}")
                    return True
                err_out = (res2.stdout + " " + res2.stderr).strip()

            # 若报 INSTALL_FAILED_USER_RESTRICTED (如小米 MIUI 拦截通过 USB install)，尝试 push 到 /data/local/tmp 然后 pm install -r
            if "INSTALL_FAILED_USER_RESTRICTED" in err_out:
                logger.info("检测到系统拦截 USB 安装，尝试转为 push + pm install -r 绕过...")
                remote_apk = f"/data/local/tmp/{apk_path.name}"
                push_cmd = [self.adb_bin]
                if device_id and device_id not in ["mock-device", "local-simulator", "default"]:
                    push_cmd.extend(["-s", device_id])
                push_cmd.extend(["push", str(apk_path), remote_apk])
                subprocess.run(push_cmd, capture_output=True, timeout=120)
                pm_cmd = [self.adb_bin]
                if device_id and device_id not in ["mock-device", "local-simulator", "default"]:
                    pm_cmd.extend(["-s", device_id])
                pm_cmd.extend(["shell", "pm", "install", "-r", remote_apk])
                res3 = subprocess.run(pm_cmd, capture_output=True, text=True, timeout=120)
                if "Success" in res3.stdout:
                    logger.info(f"APK push+pm 安装成功: {apk_path.name}")
                    return True
                err_out = (res3.stdout + " " + res3.stderr).strip()

            logger.error(f"APK 安装失败: {err_out}")
            return False
        except Exception as e:
            logger.error(f"执行 adb 安装命令异常: {e}")
            return False

    def uninstall_app(self, package_or_bundle_id: str) -> bool:
        """卸载应用"""
        if not package_or_bundle_id:
            return False
        logger.info(f"正在卸载应用: {package_or_bundle_id}")
        if self.platform == "android":
            res = subprocess.run([self.adb_bin, "uninstall", package_or_bundle_id], capture_output=True, text=True)
            return "Success" in res.stdout
        return True

    def clear_app_data(self, package_id: str) -> bool:
        """清理应用缓存与数据"""
        if self.platform == "android" and package_id:
            logger.info(f"清理应用数据: {package_id}")
            res = subprocess.run([self.adb_bin, "shell", "pm", "clear", package_id], capture_output=True, text=True)
            return "Success" in res.stdout
        return True

    def get_connected_devices(self) -> list:
        """获取已连接的设备列表"""
        devices = []
        if self.platform == "android":
            try:
                res = subprocess.run([self.adb_bin, "devices"], capture_output=True, text=True)
                for line in res.stdout.strip().split("\n")[1:]:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        devices.append(parts[0])
            except Exception as e:
                logger.warning(f"获取 adb 设备失败: {e}")
        return devices

    def is_uiautomator2_ready(self) -> bool:
        """检查真机上是否已经完整就绪 UiAutomator2 服务端驱动"""
        return self.is_app_installed("io.appium.uiautomator2.server") and self.is_app_installed("io.appium.uiautomator2.server.test")

    def ensure_uiautomator2_installed(self) -> bool:
        """确保真机上的 UiAutomator2 核心服务与测试套件完整就绪"""
        if self.is_uiautomator2_ready():
            return True
        import time
        home = Path.home()
        u2_dir = home / ".appium" / "node_modules" / "appium-uiautomator2-driver" / "node_modules" / "appium-uiautomator2-server" / "apks"
        if not u2_dir.exists():
            return False
        server_apk = u2_dir / "appium-uiautomator2-server-v10.6.6.apk"
        test_apk = u2_dir / "appium-uiautomator2-server-debug-androidTest.apk"

        for apk, pkg in [(server_apk, "io.appium.uiautomator2.server"), (test_apk, "io.appium.uiautomator2.server.test")]:
            if not self.is_app_installed(pkg) and apk.exists():
                logger.info(f"自动向真机补齐 Appium 驱动组件: {apk.name}...")
                subprocess.run([self.adb_bin, "push", str(apk), f"/data/local/tmp/{apk.name}"], capture_output=True, timeout=10)
                p = subprocess.Popen([self.adb_bin, "shell", "pm", "install", "-r", "-t", "-g", f"/data/local/tmp/{apk.name}"])
                for _ in range(8):
                    time.sleep(1)
                    if p.poll() is not None:
                        break
                    # 动态适配任意分辨率物理底栏居中确认按钮 (如 1080x2400 / 1080x2160 / 720x1600 等)
                    btn_x, btn_y = 540, 2200
                    try:
                        wm_res = subprocess.run([self.adb_bin, "shell", "wm", "size"], capture_output=True, text=True, timeout=2)
                        m_sz = re.findall(r"(\d+)x(\d+)", wm_res.stdout)
                        if m_sz:
                            w_sz, h_sz = map(int, m_sz[-1])
                            btn_x, btn_y = w_sz // 2, int(h_sz * 0.92)
                    except Exception:
                        pass
                    subprocess.run([self.adb_bin, "shell", "input", "tap", str(btn_x), str(btn_y)], capture_output=True)
                p.wait()
                subprocess.run([self.adb_bin, "shell", "input", "tap", str(btn_x), str(btn_y)], capture_output=True)
        return self.is_uiautomator2_ready()

    def get_current_foreground_app(self, device_id: str = None) -> dict:
        """获取指定设备当前前台运行的应用包名与 Activity"""
        cmd = [self.adb_bin]
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(["shell", "dumpsys", "window"])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            for line in res.stdout.splitlines():
                if "mCurrentFocus" in line or "mFocusedApp" in line:
                    m = re.search(r"([a-zA-Z0-9_\.]+)\/([a-zA-Z0-9_\.]+)", line)
                    if m:
                        return {"package": m.group(1), "activity": m.group(2)}
        except Exception:
            pass
        return {"package": "", "activity": ""}
