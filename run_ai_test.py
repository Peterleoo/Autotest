import os
import sys
import time
import argparse
import logging
from pathlib import Path

# Windows 下 stdout/stderr 被重定向到管道时默认使用 GBK，emoji 日志会触发 UnicodeEncodeError
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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

def run_test(goal: str, case_name: str, app_file: str = None, app_package: str = None, provider: str = None, auto_solidify: bool = True, device_id: str = None, session_id: str = None, turn_id: int = 1):
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
    if app_file and not target_app:
        logger.error(f"❌ 所选待测应用 [{app_file}] 不存在于 apps 目录，测试终止。请重新上传或选择应用包！")
        sys.exit(1)
    apk_info = app_mgr.get_apk_info(target_app) if target_app else {}
    pkg = apk_info.get("package") or app_package or settings.ANDROID_APP_PACKAGE
    act = apk_info.get("activity") or settings.ANDROID_APP_ACTIVITY
    print(f"🎯 [待测应用锁定] 安装包: {target_app.name if target_app else '未指定'} · 包名: {pkg} · Activity: {act}")

    is_installed = app_mgr.is_app_installed(pkg, device_id=device_id)
    local_apk_size = target_app.stat().st_size if target_app else 0
    installed_apk_size = app_mgr.get_installed_apk_size(pkg, device_id=device_id) if is_installed else 0
    # 设备上同包名但安装包大小不一致，说明装的是另一个构建（如 UI 测试包），必须覆盖为所选 APK
    build_mismatch = bool(is_installed and local_apk_size and installed_apk_size and installed_apk_size != local_apk_size)
    if is_installed and not build_mismatch:
        print(f"\n📱 [状态核实] 真机已安装应用 [{pkg}] (APK {installed_apk_size} B)，与所选安装包一致，直接调起运行！")
    else:
        if build_mismatch:
            print(f"\n⚠️ [安装包一致性] 真机现装包与所选 APK 不一致 (设备 {installed_apk_size} B / 本地 {local_apk_size} B)，自动覆盖安装所选版本...")
        if not target_app:
            logger.error(f"❌ 真机未安装应用 [{pkg}]，且未在 apps 目录下找到可供安装的安装包！测试终止。")
            print(f"\n💡 提示: 请将待测 APK 安装包放入 apps/ 目录，或提前在真机上手动安装该应用。")
            sys.exit(1)

        if settings.PLATFORM == "android":
            print(f"\n📦 开始安装所选安装包: {target_app.name} 到设备 {device_id or '默认设备'}...")
            install_ok = app_mgr.install_android_app(target_app, device_id=device_id)
            if not install_ok:
                logger.error(f"❌ 待测应用 [{target_app.name}] 安装失败！请检查设备是否在线 (USB 调试/授权) 或存储空间是否充足。测试立即终止。")
                print(f"\n💡 提示: 请确保手机屏幕解锁并已在弹窗中允许 USB 调试与应用安装。")
                sys.exit(1)

            # 安装后二次复核，杜绝假安装或装错构建
            if not app_mgr.is_app_installed(pkg, device_id=device_id):
                logger.error(f"❌ 安装命令已执行但真机校验应用 [{pkg}] 仍处于未安装状态！测试立即终止。")
                sys.exit(1)
            installed_after = app_mgr.get_installed_apk_size(pkg, device_id=device_id)
            if local_apk_size and installed_after and installed_after != local_apk_size:
                logger.error(f"❌ 安装后设备 APK ({installed_after} B) 仍与所选包 ({local_apk_size} B) 不一致，测试终止，避免误测其他构建。")
                sys.exit(1)
            print(f"✅ [应用就绪] 待测应用 [{pkg}] 安装并校验通过！")

    # 2. 检查是否有已连接的设备或正在运行的 Appium Server
    driver = None
    try:
        # 🛡️ 对标 DeepSeek 机制：连续对话 (turn_id > 1) 原地继承真机当前屏幕，严禁退回桌面重复冷启动！
        should_cold_launch = (turn_id <= 1)
        driver = DriverFactory.create_driver(
            app_path=str(target_app) if not is_installed and target_app else None,
            package_name=pkg,
            activity_name=act if should_cold_launch else None,
            device_id=device_id,
            auto_launch=should_cold_launch
        )

        # 续测或界面漂移时强制回到所选应用，杜绝误测桌面上其他 App
        if pkg and act and hasattr(driver, "get_current_app") and hasattr(driver, "launch_app"):
            current_focus = driver.get_current_app()
            if current_focus and pkg not in current_focus:
                print(f"🔄 当前前台并非待测应用 ({current_focus.strip()})，自动切回 [{pkg}] ...")
                driver.launch_app(pkg, act)
                time.sleep(0.8)

        # 最终核验：待测应用必须在前台，否则终止，绝不让 AI 去桌面上误点其他 App
        if pkg and act and hasattr(driver, "get_current_app"):
            final_focus = driver.get_current_app()
            if final_focus and pkg not in final_focus:
                logger.error(f"❌ 待测应用 [{pkg}] 未能切到前台，当前界面: {final_focus.strip()}。已终止，避免误测其他应用。")
                raise RuntimeError(f"待测应用 [{pkg}] 未在前台")
    except Exception as e:
        logger.error(f"连接驱动失败: {e}")
        print("\n💡 提示: 请确保设备正常在线且开启 USB 调试。")
        sys.exit(1)

    try:
        # 3. 提取会话记忆上下文 (Conversation Memory)
        memory_context = ""
        if session_id:
            from pathlib import Path
            import json
            sess_file = Path("data/sessions") / f"{session_id}.json"
            if not sess_file.exists():
                sess_file = Path("outputs/sessions") / f"{session_id}.json"
            if sess_file.exists():
                try:
                    sess_data = json.loads(sess_file.read_text(encoding="utf-8"))
                    from core.memory_manager import MemoryManager
                    memory_context = MemoryManager.build_memory_context(sess_data)
                    est_t = MemoryManager.estimate_tokens(memory_context)
                    print(f"🧠 [记忆注入] 已载入会话 [{session_id}] 结构化历史事实与目标演进链 (约 {est_t} Tokens)")
                except Exception as e:
                    logger.warning(f"载入会话记忆异常: {e}")

        # 4. 运行 AI 智能体 (传入连续上下文)
        agent = AITestAgent(driver=driver, llm_provider=provider, app_identifier=app_file, session_id=session_id)
        result = agent.run_goal(goal, memory_context=memory_context)

        # 4. 后期固化为标准测试脚本 (仅当测试真正成功且具备执行历史时才予以固化沉淀)
        if result.get("success"):
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
        else:
            print("\n⚠️ 测试目标未达成或执行受阻中断，已跳过自动化用例固化流程。")
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
    parser.add_argument("--package", "-k", type=str, default=None, help="显式指定待测应用包名")
    parser.add_argument("--device", "-d", type=str, default=None, help="指定运行的目标设备序列号")
    parser.add_argument("--provider", "-p", type=str, default=None, help="AI 模型提供商 (claude / deepseek / antigravity / openai)")
    parser.add_argument("--no-solidify", action="store_true", help="不自动生成固化脚本")
    parser.add_argument("--session-id", type=str, default=None, help="关联的 Web 会话 ID")
    parser.add_argument("--turn-id", type=int, default=1, help="当前执行的交互轮次 (Turn)")

    args = parser.parse_args()
    run_test(
        goal=args.goal,
        case_name=args.name,
        app_file=args.app,
        app_package=args.package,
        device_id=args.device,
        provider=args.provider,
        auto_solidify=not args.no_solidify,
        session_id=args.session_id,
        turn_id=args.turn_id
    )
