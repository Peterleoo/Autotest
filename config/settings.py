import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 环境变量（如果存在）
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# 自动检测并注入 Android SDK 环境变量（跨平台用户目录与多路径自适应寻址）
home = Path.home()
candidate_sdks = []
for env_key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
    env_val = os.environ.get(env_key, "").strip()
    if env_val:
        candidate_sdks.append(Path(env_val))
candidate_sdks.extend([
    home / "AppData/Local/Android/Sdk",
    home / "Android/Sdk",
    Path("/usr/local/share/android-sdk"),
    Path("/opt/android-sdk")
])
for sdk in candidate_sdks:
    # 必须是真实 SDK 目录，避免空环境变量被 Path("") 解析成 "." 后误命中
    if not sdk.is_dir():
        continue
    if not ((sdk / "platform-tools").is_dir() or (sdk / "build-tools").is_dir()):
        continue
    os.environ["ANDROID_HOME"] = str(sdk)
    os.environ["ANDROID_SDK_ROOT"] = str(sdk)
    pt_dir = str(sdk / "platform-tools")
    if pt_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = pt_dir + os.pathsep + os.environ.get("PATH", "")
    break

class Settings:
    # 基础目录
    BASE_DIR: Path = BASE_DIR
    APPS_DIR: Path = BASE_DIR / "apps"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    SOLIDIFIED_DIR: Path = BASE_DIR / "tests" / "solidified"

    # 测试目标平台：'android' 或 'ios'
    PLATFORM: str = os.getenv("TARGET_PLATFORM", "android").lower()

    # Appium Server 地址
    # 本地 Android 默认为 http://127.0.0.1:4723
    # 局域网 Mac 上的 iOS 可配置为 http://<MAC_IP>:4723
    APPIUM_SERVER_URL: str = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")

    # Android 配置
    ANDROID_DEVICE_NAME: str = os.getenv("ANDROID_DEVICE_NAME", "Android_Device")
    ANDROID_PLATFORM_VERSION: str = os.getenv("ANDROID_PLATFORM_VERSION", "14.0")
    ANDROID_AUTOMATION_NAME: str = "UiAutomator2"
    # 待测应用信息
    ANDROID_APP_NAME: str = os.getenv("ANDROID_APP_NAME", "demo_app.apk")
    ANDROID_APP_PACKAGE: str = os.getenv("ANDROID_APP_PACKAGE", "")
    ANDROID_APP_ACTIVITY: str = os.getenv("ANDROID_APP_ACTIVITY", "")

    # iOS 配置（指向局域网 Mac 机器上的 WebDriverAgent 节点）
    IOS_DEVICE_NAME: str = os.getenv("IOS_DEVICE_NAME", "iPhone 15")
    IOS_PLATFORM_VERSION: str = os.getenv("IOS_PLATFORM_VERSION", "17.0")
    IOS_AUTOMATION_NAME: str = "XCUITest"
    IOS_UDID: str = os.getenv("IOS_UDID", "")
    IOS_BUNDLE_ID: str = os.getenv("IOS_BUNDLE_ID", "")
    IOS_APP_NAME: str = os.getenv("IOS_APP_NAME", "")

    # 接口测试 Base URL 与默认请求头
    API_BASE_URL: str = os.getenv("API_BASE_URL", "https://httpbin.org")
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "15"))

    # 超时设置（秒）
    ELEMENT_WAIT_TIMEOUT: int = int(os.getenv("ELEMENT_WAIT_TIMEOUT", "10"))
    ACTION_INTERVAL: float = float(os.getenv("ACTION_INTERVAL", "1.0"))

settings = Settings()
