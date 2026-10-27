import sys
import subprocess
from pathlib import Path

# 添加工程根目录
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.app_manager import AppManager

def inspect_devices():
    app_mgr = AppManager()
    adb = app_mgr.adb_bin
    print("=" * 60)
    print("📱 真机设备检测与连接诊断工具")
    print("=" * 60)

    res = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True)
    lines = [line.strip() for line in res.stdout.strip().split("\n")[1:] if line.strip()]

    if not lines:
        print("\n⚠️  当前未检测到已连接的 Android 真机或模拟器。")
        print("\n👉 真机连接指引:")
        print("  1. 手机打开【设置】->【关于手机】-> 连续点击【版本号】5-7次开启开发者模式。")
        print("  2. 进入【系统/更多设置】->【开发者选项】-> 打开【USB 调试】和【允许通过 USB 安装应用】。")
        print("  3. 使用 USB 数据线连接电脑，手机弹出'允许 USB 调试吗'时勾选【始终允许】并点击确定。")
        print("  4. 若需【无线调试】：可先插线运行 `adb tcpip 5555`，拔掉线后运行 `adb connect <手机IP>:5555`。")
        return []

    print(f"\n✅ 检测到 {len(lines)} 台在线设备:\n")
    devices = []
    for i, line in enumerate(lines, 1):
        parts = line.split()
        dev_id = parts[0]
        model = "未知型号"
        for p in parts[1:]:
            if p.startswith("model:"):
                model = p.replace("model:", "").replace("_", " ")

        # 进一步读取设备品牌与安卓版本
        brand = subprocess.run([adb, "-s", dev_id, "shell", "getprop", "ro.product.brand"], capture_output=True, text=True).stdout.strip()
        version = subprocess.run([adb, "-s", dev_id, "shell", "getprop", "ro.build.version.release"], capture_output=True, text=True).stdout.strip()
        wm_size = subprocess.run([adb, "-s", dev_id, "shell", "wm", "size"], capture_output=True, text=True).stdout.strip()
        resolution = wm_size.split(":")[-1].strip() if ":" in wm_size else "未知"

        print(f"  [{i}] 设备序列号: {dev_id}")
        print(f"      设备机型: {brand.upper()} {model}")
        print(f"      系统版本: Android {version}")
        print(f"      屏幕分辨率: {resolution}")
        print("-" * 50)
        devices.append(dev_id)

    return devices

def install_and_launch_demo_app(device_id: str = None):
    app_mgr = AppManager()
    adb = app_mgr.adb_bin
    apks = list((BASE_DIR / "apps").glob("*.apk"))

    if not apks:
        print("❌ apps 目录下未找到任何 APK 安装包")
        return

    apk_path = apks[0]
    info = app_mgr.get_apk_info(apk_path)
    pkg = info.get("package") or "com.example.app"
    act = info.get("activity") or "com.example.app.MainActivity"

    cmd = [adb]
    if device_id:
        cmd.extend(["-s", device_id])
    
    print(f"\n🚀 正在向真机推送安装待测应用 [{apk_path.name}]...")
    cmd.extend(["install", "-r", "-g", str(apk_path)])
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    print("安装结果:", res.stdout.strip())

    if "Success" in res.stdout:
        print("\n🎉 安装成功！正在自动启动应用...")
        launch_cmd = [adb]
        if device_id:
            launch_cmd.extend(["-s", device_id])
        launch_cmd.extend(["shell", "am", "start", "-n", f"{pkg}/{act}"])
        launch_res = subprocess.run(launch_cmd, capture_output=True, text=True)
        print("启动输出:", launch_res.stdout.strip())
        print(f"✅ 待测应用 [{pkg}] 已成功在真机前台运行，可以随时开始 AI 自动化测试！")

if __name__ == "__main__":
    devs = inspect_devices()
    if devs:
        choice = input("\n是否立即安装并启动待测应用到第 1 台设备? (y/n): ").strip().lower()
        if choice == "y":
            install_and_launch_demo_app(devs[0])
