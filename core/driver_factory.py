import logging
from typing import Optional
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from config.settings import settings

logger = logging.getLogger("DriverFactory")

class DriverFactory:
    """
    负责创建和配置 Appium WebDriver 实例（统一调度 Android 和 iOS）
    """
    @staticmethod
    def create_driver(
        platform: Optional[str] = None,
        app_path: Optional[str] = None,
        package_name: Optional[str] = None,
        activity_name: Optional[str] = None,
        device_id: Optional[str] = None,
        auto_launch: bool = True
    ) -> webdriver.Remote:
        plat = (platform or settings.PLATFORM).lower()
        server_url = settings.APPIUM_SERVER_URL

        logger.info(f"正在为平台 [{plat}] 连接驱动 (目标设备: {device_id or '自动识别'}) ...")

        if plat == "android":
            pkg = package_name or settings.ANDROID_APP_PACKAGE
            act = activity_name or settings.ANDROID_APP_ACTIVITY

            # 🚀 第一性原理突破：优先使用零安装、零弹窗、免疫一切厂商拦截的原生 ADB 极速真机驱动！
            try:
                from core.native_adb_driver import NativeADBDriver
                native_driver = NativeADBDriver(device_id=device_id)
                if native_driver.device_id:
                    logger.info(f"✨ 成功激活原生 ADB 极速真机驱动 [设备: {native_driver.device_id}]，免驱动安装，彻底免疫弹窗！")
                    if auto_launch and pkg:
                        native_driver.launch_app(pkg, act)
                    else:
                        logger.info(f"⚡ [就地接管] 保持目标应用 [{pkg}] 当前真机界面，跳过重复冷启动！")
                    return native_driver
            except Exception as e:
                logger.warning(f"原生 ADB 驱动不可用 ({e})，降级尝试 Appium...")

            options = UiAutomator2Options()
            options.platform_name = "Android"
            options.automation_name = settings.ANDROID_AUTOMATION_NAME
            options.device_name = settings.ANDROID_DEVICE_NAME
            options.no_reset = True
            options.full_reset = False
            options.new_command_timeout = 300

            # 优先使用已安装的包名与主界面直接调起（杜绝每次重装弹窗）
            pkg = package_name or settings.ANDROID_APP_PACKAGE
            act = activity_name or settings.ANDROID_APP_ACTIVITY
            if pkg and act:
                options.app_package = pkg
                options.app_activity = act
                logger.info(f"直接调起真机已安装应用: {pkg} / {act}")
            elif app_path:
                options.app = str(app_path)

            driver = webdriver.Remote(command_executor=server_url, options=options)
            driver.implicitly_wait(settings.ELEMENT_WAIT_TIMEOUT)
            logger.info("Android Appium Driver 创建成功")
            return driver

        elif plat == "ios":
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.automation_name = settings.IOS_AUTOMATION_NAME
            options.device_name = settings.IOS_DEVICE_NAME
            options.platform_version = settings.IOS_PLATFORM_VERSION
            options.new_command_timeout = 300

            if settings.IOS_UDID:
                options.udid = settings.IOS_UDID
            if app_path:
                options.app = str(app_path)
            elif settings.IOS_BUNDLE_ID:
                options.bundle_id = settings.IOS_BUNDLE_ID

            driver = webdriver.Remote(command_executor=server_url, options=options)
            driver.implicitly_wait(settings.ELEMENT_WAIT_TIMEOUT)
            logger.info("iOS Appium Driver 创建成功")
            return driver

        else:
            raise ValueError(f"不支持的平台类型: {plat}")
