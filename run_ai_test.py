import os
import sys
import argparse
import logging
from pathlib import Path

# 添加工程根目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config.settings import settings
from config.ai_config import ai_config
from core.app_manager import AppManager
from core.driver_factory import DriverFactory
from ai_engine.test_agent import AITestAgent
from ai_engine.solidifier import Solidifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MainRunner")

def run_test(goal: str, case_name: str, app_file: str = None, provider: str = None, auto_solidify: bool = True, device_id: str = None):
    print("=" * 60)
    print(f"🤖 AI 移动端全自动测试与固化引擎")
    print(f"🎯 测试目标: {goal}")
    print(f"🏷️  用例名称: {case_name}")
    print(f"📱 目标平台: {settings.PLATFORM.upper()} (设备: {device_id or '默认设备'})")
    print(f"🧠 模型服务: {(provider or ai_config.PROVIDER).upper()}")
    print("=" * 60)

    # 1. 检查并安装应用（避免重复安装）
    app_mgr = AppManager()
    target_app = app_mgr.find_target_app(app_file)
    apk_info = app_mgr.get_apk_info(target_app) if target_app else {}
    pkg = apk_info.get("package") or settings.ANDROID_APP_PACKAGE
    act = apk_info.get("activity") or settings.ANDROID_APP_ACTIVITY

    is_installed = app_mgr.is_app_installed(pkg, device_id=device_id)
    if is_installed:
        print(f"\n📱 [状态核实] 真机已安装应用 [{pkg}]，直接调起运行，无需重复安装！")
    else:
        if not target_app:
            logger.error(f"❌ 真机未安装应用 [{pkg}]，且未在 apps 目录下找到可供安装的安装包！测试终止。")
            print(f"\n💡 提示: 请将待测 APK 安装包放入 apps/ 目录，或提前在真机上手动安装该应用。")
            sys.exit(1)

        if settings.PLATFORM == "android":
            print(f"\n📦 真机未检测到应用，开始初次安装: {target_app.name} 到设备 {device_id or '默认设备'}...")
            install_ok = app_mgr.install_android_app(target_app, device_id=device_id)
            if not install_ok:
                logger.error(f"❌ 待测应用 [{target_app.name}] 安装失败！请检查设备是否在线 (USB 调试/授权) 或存储空间是否充足。测试立即终止。")
                print(f"\n💡 提示: 请确保手机屏幕解锁并已在弹窗中允许 USB 调试与应用安装。")
                sys.exit(1)

            # 安装后二次复核，杜绝假安装
            if not app_mgr.is_app_installed(pkg, device_id=device_id):
                logger.error(f"❌ 安装命令已执行但真机校验应用 [{pkg}] 仍处于未安装状态！测试立即终止。")
                sys.exit(1)
            print(f"✅ [应用就绪] 待测应用 [{pkg}] 安装并校验通过！")

    # 2. 检查是否有已连接的设备或正在运行的 Appium Server
    driver = None
    try:
        driver = DriverFactory.create_driver(
            app_path=str(target_app) if not is_installed and target_app else None,
            package_name=pkg,
            activity_name=act,
            device_id=device_id
        )
    except Exception as e:
        logger.error(f"连接驱动失败: {e}")
        print("\n💡 提示: 请确保设备正常在线且开启 USB 调试。")
        sys.exit(1)

    try:
        # 3. 运行 AI 智能体
        agent = AITestAgent(driver=driver, llm_provider=provider)
        result = agent.run_goal(goal)

        # 4. 后期固化为标准测试脚本
        if auto_solidify and result.get("history"):
            print(f"\n💾 正在将测试动作轨迹固化为原生 Pytest 测试脚本...")
            solid_file = Solidifier.solidify_test_case(
                case_name=case_name,
                goal=goal,
                action_history=result["history"]
            )
            print(f"🎉 固化成功！生成文件: {solid_file}")
            print(f"👉 后续可直接使用原生命令极速回归运行（无需再次调用 AI）:")
            print(f"   pytest {solid_file} -v -s")

        if not result.get("success"):
            err_reason = result.get("error_reason")
            if err_reason:
                logger.error(f"❌ 测试受阻详情:\n{err_reason}")
            else:
                logger.error("❌ AI 自动化测试未能达成预期目标！")
            sys.exit(1)

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI 移动端自动化测试与脚本固化工具")
    parser.add_argument("--goal", "-g", type=str, default="打开应用，完成账号登录注册流程，并验证用户信息接口", help="测试目标描述")
    parser.add_argument("--name", "-n", type=str, default="login_register_flow", help="固化测试用例英文标识名")
    parser.add_argument("--app", "-a", type=str, default=None, help="apps 目录下的指定安装包文件名")
    parser.add_argument("--device", "-d", type=str, default=None, help="指定运行的目标设备序列号")
    parser.add_argument("--provider", "-p", type=str, default=None, help="AI 模型提供商 (claude / deepseek / antigravity / openai)")
    parser.add_argument("--no-solidify", action="store_true", help="不自动生成固化脚本")

    args = parser.parse_args()
    run_test(
        goal=args.goal,
        case_name=args.name,
        app_file=args.app,
        device_id=args.device,
        provider=args.provider,
        auto_solidify=not args.no_solidify
    )
