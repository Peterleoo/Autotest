import time
import json
import logging
import subprocess
from typing import Optional, List, Dict, Any
from appium import webdriver

from core.llm_client import LLMClient
from core.api_client import APIClient
from ai_engine.screen_parser import ScreenParser
from ai_engine.action_executor import ActionExecutor
from core.app_lessons_manager import app_lessons_mgr

logger = logging.getLogger("AITestAgent")

SYSTEM_PROMPT = """
你是一个资深的移动应用自动化测试 AI 智能体。你的任务是根据用户的【测试目标】，分析当前移动设备屏幕截图与视觉识别出的文字元素，进行高智力、有条理的自动化测试决策。

你支持以下操作类型（Action）：
1. tap: 点击元素。需指定 target_index（元素编号）或 coordinates ([x, y])。优先使用 target_index。
2. type: 在文本框中输入。需指定 target_index 和 text（输入的文本）。
3. swipe: 滑动手势。需指定 direction ("up" / "down" / "left" / "right")，可选 repeat（连续重复次数，例如 {"action": "swipe", "direction": "up", "repeat": 2}，用于长列表连滑浏览）。
4. fast_forward_guide: 引导页极速穿透宏动作。当识别为新用户多页轮播引导页时优先使用，端侧自动连翻3页并轻触体验/跳过，一步直接穿透至主页！
5. press_key: 按键模拟。例如 {"action": "press_key", "key": "back"}。
6. wait: 等待页面加载。例如 {"action": "wait", "seconds": 2}。
7. call_api: 接口测试/数据交互。例如 {"action": "call_api", "method": "POST", "endpoint": "/api/v1/login", "json": {"user":"a"}, "expected_status": 200}。
8. assert_text: 文本断言。例如 {"action": "assert_text", "expected": "首页", "reason": "断言是否成功跳转"}。
9. finish: 当测试目标已经全部达成且验证通过时返回。例如 {"action": "finish", "reason": "已完整走通登录流程并断言成功"}。


🔥 核心决策守则（严格遵守，严禁在 App 内盲目乱跳）：
0. 【DSH 反伪造达成铁律】：
    - 严禁掩耳盗铃！若用户的测试目标要求验证具体业务界面（如：进入房源详情、查看VR、点击咨询弹出咨询窗口、进入个人中心等），而当前真机屏幕仍停留在【登录/注册页、密码输入页、验证码拦截弹窗或网络报错页】，严禁将“拉起了登录拦截/权限控制正常”诡辩为“目标已达成”并调用 finish！
    - 系统配备了独立的 DSH 核验门禁（TaskVerifier），任何在拦截页面擅自调用 finish 的企图都会被一票否决！
    - 若当前处于登录页，优先识别输入框调用 type 注入预设账号密码登录，或点击一键登录放行；只有真正进入目标业务窗口后方可调用 finish！
1. 【界面定性】：在 thought 中第一句必须明确输出：“【当前界面判断】：xxx界面（如：应用手机号登录页/首页推荐/隐私协议弹窗）”。
2. 【目标驱动，严禁乱跳】：
    - 紧扣用户的【测试目标】！不要点击与目标无关的广告或偏门入口。
    - 针对新用户多页引导页/轮播图：严禁每滑一页就停下来重新截屏识别一次！只要定性为引导页，果断直接下发 {"action": "fast_forward_guide", "reason": "新用户引导页极速穿透直达首页"} 或 {"action": "swipe", "direction": "left", "repeat": 3}，一步到位直接翻到最后一页并进入应用首页！
    - 针对长列表浏览：若目标需浏览推荐列表或信息流，可直接使用 repeat 连续滑动（如 {"action": "swipe", "direction": "up", "repeat": 2}），一气呵成减少交互轮次。
    - 针对登录流程：若有协议勾选先点击协议勾选 -> 点击手机号输入框输入测试号码 -> 点击获取验证码/用密码登录 -> 验证跳转。
    - 针对搜索流程：若当前不在首页（例如误入“委托服务”或“我的”页面），第一步必须先按返回键 {"action": "press_key", "key": "back"} 或点击底部【首页】Tab 回到主页；然后在主页顶部点击搜索框（带有“搜索”或“请输入小区名”）进入搜索页面；在搜索页面，可直接点击下方的【热门搜索】条目（如‘钰龙天下’、‘华润凤凰城’、‘星城国际’）或搜索联想条目，即可一键直达房源搜索结果列表；在房源列表中执行下拉滑动或文本断言（如包含‘万’、‘室’、‘m²’等房源信息），达成目标后果断调用 finish 完成测试！
    - 针对表单录入与必填校验：长表单页面的“免费发布/立即提交”按钮往往固定在屏幕最底部的悬浮操作条（Sticky Bottom Bar）中。严禁在上下滑动中盲目震荡！若表单项已就绪，优先点击页面底部的提交/发布按钮触发必填校验；达成必填校验拦截后，果断调用 finish 完成测试！
    - 针对表单智能推断填充：常规输入框（姓名、手机号、期望售价、租金、面积、小区等），系统内置智能推断引擎，可直接下发 type 动作并给出标准测试值（如手机号 13800138000，姓名 张先生，售价 300，面积 98），系统将秒级合规上屏，严禁停滞等待人工输入！
    - 针对委托服务区：严禁在未要求测试委托服务时点击委托房源或委托卡片！若要求测试委托服务但首页金刚区未看到，优先在金刚区区域执行一次向左滑动手势 (swipe left) 翻页！
3. 【坐标精准感知】：元素列表中附带了视觉 OCR 探测出的屏幕精确物理坐标 [x, y]，你可以直接基于编号或坐标点击。
4. 【禁止无意义刷步与盲目滑动】：严禁原地重复上下滑动；达成业务目标后应果断调用 finish 完成测试。
5. 输出格式必须是纯 JSON，不要包含任何 markdown 代码块包裹或解释文本。

JSON 输出格式样例：
{
  "thought": "【当前界面判断】：应用登录授权界面。当前页面有手机号输入框[编号5]和隐私协议[编号10]，先点击勾选隐私政策协议。",
  "action": "tap",
  "target_index": 10,
  "reason": "勾选同意用户服务与隐私协议"
}
"""

class AITestAgent:
    """
    AI 驱动测试智能体：零门槛驱动移动端交互、功能及接口测试
    """
    def __init__(self, driver: webdriver.Remote, llm_provider: Optional[str] = None, status_callback: Optional[Any] = None, app_identifier: Optional[str] = None, session_id: Optional[str] = None):
        self.driver = driver
        self.llm = LLMClient(provider=llm_provider)
        self.api_client = APIClient()
        self.app_identifier = app_identifier
        self.session_id = session_id
        # 提取目标应用元数据供大模型决策精准感知
        self.app_info = {}
        if self.app_identifier:
            try:
                from core.app_manager import AppManager
                app_mgr = AppManager()
                target_apk = app_mgr.find_target_app(self.app_identifier)
                if target_apk:
                    self.app_info = app_mgr.get_apk_info(target_apk)
            except Exception as e:
                logger.debug(f"获取待测包元数据跳过: {e}")
        self.executor = ActionExecutor(driver=self.driver, api_client=self.api_client, app_identifier=app_identifier)
        self.status_callback = status_callback
        self._has_prompted_credential = False

    def _notify_status(self, data: Dict[str, Any]):
        if self.status_callback:
            try:
                self.status_callback(data)
            except Exception as e:
                logger.warning(f"状态回调异常: {e}")


    def _execute_credential_injection(self, acc: str, pwd: str, screen_info: Dict[str, Any]) -> bool:
        """
        确定性端侧凭证自动注入流水线 (DSH Credential Injection Pipeline)
        真实模拟用户物理操作：切换密码登录 -> 勾选协议 -> 填手机号 -> 填密码 -> 提交登录
        """
        logger.info(f"🔑 [DSH 凭证自动注入] 开始对真机执行账号 [{acc}] 真实登录注入流水线...")
        self._notify_status({
            "step": 0,
            "action": "自动登录注入",
            "log": f"🔑 正在自动填入测试凭证 [{acc}] 并执行物理登录..."
        })

        # 1. 检查是否在验证码登录模式，若有'密码登录'/'账号密码登录'切换按钮，先切换
        for el in screen_info.get("elements", []):
            t = (el.get("text") or el.get("content_desc") or "").strip()
            if any(k in t for k in ["用密码登录", "密码登录", "账号密码登录"]):
                logger.info(f"点击切换到密码登录模式: {t}")
                self.executor._locate_and_click(el, None)
                time.sleep(0.6)
                screen_info = ScreenParser.get_screen_summary(self.driver)
                break

        # 2. 扫描定位关键组件：手机号框、密码框、协议框、登录按钮
        phone_el, pwd_el, agree_el, login_btn = None, None, None, None
        for el in screen_info.get("elements", []):
            t = (el.get("text") or el.get("content_desc") or "").strip()
            if not phone_el and any(k in t for k in ["手机号", "账号", "请输入手机", "请输入账号"]):
                phone_el = el
            elif not pwd_el and any(k in t for k in ["密码", "请输入密码"]):
                pwd_el = el
            elif not agree_el and any(k in t for k in ["协议", "同意", "已阅读"]):
                agree_el = el
            elif not login_btn and any(k in t for k in ["登录", "进入"]):
                # 排除"密码登录"等切换按钮
                if not any(k in t for k in ["密码登录", "切换", "验证码登录"]):
                    login_btn = el

        # 3. 执行物理点击协议
        if agree_el:
            logger.info("勾选服务与隐私协议")
            self.executor._locate_and_click(agree_el, None)
            time.sleep(0.3)

        # 4. 执行填入账号
        if phone_el and acc:
            logger.info(f"填入账号: {acc}")
            self.executor._locate_and_type(phone_el, acc)
            time.sleep(0.4)

        # 5. 执行填入密码
        if pwd_el and pwd:
            logger.info("填入密码: ******")
            self.executor._locate_and_type(pwd_el, pwd)
            time.sleep(0.4)

        # 6. 点击登录提交按钮
        if login_btn:
            logger.info("点击登录提交按钮")
            self.executor._locate_and_click(login_btn, None)
            time.sleep(2.0)
        else:
            # 兜底：尝试按回车或根据坐标点击
            logger.info("未明确检出登录按钮，尝试发送回车键提交")
            try:
                self.driver.press_keycode(66) # KEYCODE_ENTER
                time.sleep(1.5)
            except Exception:
                pass

        # 7. 复核是否已成功跳出登录界面
        after_screen = ScreenParser.get_screen_summary(self.driver)
        after_texts = [e.get("text", "") for e in after_screen.get("elements", [])]
        is_still_login = any(any(kw in t for kw in ["手机号登录", "密码登录", "请输入密码"]) for t in after_texts)

        if not is_still_login:
            logger.info("🎉 [DSH 凭证自动注入] 验证通过：已成功完成登录并跳出鉴权拦截页！")
            self._notify_status({
                "step": 0,
                "action": "登录完成",
                "log": "✅ 测试凭证自动注入完成，真机已成功跨过登录拦截，业务链路恢复流转！"
            })
            return True
        else:
            logger.warning("⚠️ [DSH 凭证自动注入] 尝试注入后真机仍停留在登录页，可能存在图形滑块验证码或密码校验失败")
            return False

    def _check_and_prompt_hitl_credential(self, screen_info: Dict[str, Any], goal: str) -> bool:
        """
        人机协同登录决策拦截门禁 (Human-in-the-Loop Credential Gate)
        若真机界面进入账号密码/验证码登录页面：
        1. 优先检索当前 App 是否已在设置中心配置预设真实凭证，若有则自动静默注入，保持 100% 无人值守；
        2. 若未配置凭证，立即挂起任务流，向前端发出协同信号唤出【人机协同决策卡片】，等待用户输入或投屏手动接管。
        """
        if getattr(self, "_has_prompted_credential", False):
            return False

        texts = [e.get("text", "") or e.get("content_desc", "") for e in screen_info.get("elements", [])]
        combined = " ".join(texts)

        # 识别登录页特征
        is_login_screen = any(kw in combined for kw in ["手机号登录", "密码登录", "账号密码登录", "获取验证码", "请输入手机号码", "请输入手机号", "验证码登录", "立即登录", "快捷登录"])
        if not is_login_screen and not any(kw in goal for kw in ["登录", "账号", "密码", "鉴权"]):
            return False

        if is_login_screen:
            from core.credential_manager import CredentialManager
            app_key = self.app_identifier or "demo_app"
            cred = CredentialManager.get_credential(app_key)
            if cred and cred.get("account"):
                logger.info(f"🔑 [预设凭证生效] 检测到登录界面，命中 App [{app_key}] 预置测试账号 [{cred['account']}]，立即执行端侧自动注入流水线！")
                injected = self._execute_credential_injection(cred.get("account", ""), cred.get("password", ""), screen_info)
                if injected:
                    return True
                logger.warning(f"⚠️ [自动注入未能成功跳出] 界面可能需要短信验证码、滑块拼图或人工确认，无缝转入人机协同决策卡片！")

            session_id = self.session_id or "default_session"
            logger.info("🛡️ [人机协同介入] 检测到应用进入登录界面且未预置凭证，挂起测试并等待人工决策...")
            print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}\n", flush=True)

            self._notify_status({
                "step": 0,
                "action": "人机协同介入",
                "log": "⏸️ 检测到目标应用进入账号密码登录页，已唤起人机协同决策卡片，等待用户输入凭证或在投屏手动登录..."
            })

            from pathlib import Path
            import json
            decision_file = Path(__file__).resolve().parent.parent / "scratch" / f"decision_{session_id}.json"
            if decision_file.exists():
                try: decision_file.unlink()
                except Exception: pass

            wait_start = time.time()
            while time.time() - wait_start < 300:
                if decision_file.exists():
                    try:
                        data = json.loads(decision_file.read_text(encoding="utf-8"))
                        if data.get("status") == "RESOLVED":
                            decision_type = data.get("decision_type", "inject")
                            logger.info(f"✅ [人机协同] 收到用户决策响应: {decision_type}")
                            
                            if decision_type == "inject":
                                acc = data.get("account", "").strip()
                                pwd = data.get("password", "").strip()
                                if acc:
                                    logger.info(f"💉 注入用户提供的测试账号: {acc}")
                                    phone_el, pwd_el, agree_el, login_btn = None, None, None, None
                                    for el in screen_info.get("elements", []):
                                        t = (el.get("text") or el.get("content_desc") or "").strip()
                                        if any(k in t for k in ["手机号", "账号", "请输入手机"]):
                                            phone_el = el
                                        elif any(k in t for k in ["密码", "请输入密码"]):
                                            pwd_el = el
                                        elif any(k in t for k in ["协议", "同意"]):
                                            agree_el = el
                                        elif any(k in t for k in ["登录", "进入"]):
                                            login_btn = el
                                    
                                    if agree_el:
                                        self.executor._locate_and_click(agree_el, None)
                                        time.sleep(0.5)
                                    if phone_el:
                                        self.executor._locate_and_type(phone_el, acc)
                                        time.sleep(0.5)
                                    if pwd and pwd_el:
                                        self.executor._locate_and_type(pwd_el, pwd)
                                        time.sleep(0.5)
                                    if login_btn:
                                        self.executor._locate_and_click(login_btn, None)
                                        time.sleep(1.5)
                            elif decision_type == "manual_done":
                                logger.info("✅ 用户已在投屏手动完成登录，继续自动化测试")
                                time.sleep(1.5)
                            elif decision_type == "skip":
                                logger.info("⏩ 用户选择跳过登录，模拟返回键继续")
                                try: self.driver.back()
                                except Exception: pass
                                time.sleep(1.0)

                            self._has_prompted_credential = True
                            try: decision_file.unlink()
                            except Exception: pass
                            return True
                    except Exception as e:
                        logger.warning(f"读取人机协同决策文件异常: {e}")
                time.sleep(1.0)

            logger.warning("⚠️ 等待人机协同超时 (300s)，降级为默认流程继续")
            self._has_prompted_credential = True
            return False

    def _ensure_home_context_if_needed(self, goal: str, screen_info: Dict[str, Any]):
        """若测试目标要求在首页或搜索，但当前检测到处于委托服务等二级页面，执行自动自愈返回"""
        if any(k in goal for k in ["首页", "搜索", "找房", "二手房", "新房", "租房"]):
            texts = [e.get("text", "") for e in screen_info.get("elements", [])]
            # 判断是否误入委托服务二级页面
            in_weituo = any("委托服务" in t or "线上委托" in t for t in texts)
            has_search = any("搜索" in t or "请输入小区" in t for t in texts)
            if in_weituo and not has_search:
                logger.info("🛡️ [自愈保护] 检测到当前处于【委托服务】二级页面，自动模拟返回键回到首页主界面...")
                self._notify_status({
                    "step": 0,
                    "action": "自愈归位",
                    "log": "🛡️ 检测到当前滞留在委托服务二级页面，自动按返回键归位至应用首页"
                })
                try:
                    self.driver.back()
                    time.sleep(1.0)
                except Exception:
                    pass

    def run_goal(self, goal: str, max_steps: int = 15, memory_context: Optional[str] = None) -> Dict[str, Any]:
        """
        根据自然语言目标执行自动化测试主循环
        """
        logger.info(f"========== 开始 AI 驱动自动化测试 ==========")
        logger.info(f"目标: {goal}")
        
        # 📚 自动匹配并注入应用寻路与踩坑经验 (App Lessons Engine)
        app_lessons = app_lessons_mgr.get_matched_lessons(self.app_identifier or "demo_app", goal)
        lessons_context = ""
        if app_lessons:
            lessons_context = "\n\n【专家寻路与避坑先验知识 (Lessons)】:\n" + "\n".join(f"- {l}" for l in app_lessons)
            logger.info(f"📚 成功注入 {len(app_lessons)} 条应用寻路与自愈先验经验")
        logger.info(f"使用模型提供商: {self.llm.provider} ({self.llm.model_name})")
        self._notify_status({
            "step": 0,
            "max_steps": max_steps,
            "goal": goal,
            "action": "初始化",
            "log": f"启动测试智能体，模型: {self.llm.provider} ({self.llm.model_name})"
        })

        step_count = 0
        execution_success = False
        consecutive_unchanged_screens = 0
        final_block_reason = ""

        while step_count < max_steps:
            step_count += 1
            logger.info(f"\n--- [Step {step_count}/{max_steps}] 感知界面与决策 ---")
            self._notify_status({
                "step": step_count,
                "max_steps": max_steps,
                "action": "视觉截屏感知",
                "log": f"--- [Step {step_count}/{max_steps}] 正在捕获屏幕并进行视觉 OCR 识别 ---"
            })

            # 1. 感知当前屏幕与元素
            screen_info = ScreenParser.get_screen_summary(self.driver)

            # 🛡️ 步骤前置：检查并触发人机协同登录凭证门禁
            hitl_resolved = self._check_and_prompt_hitl_credential(screen_info, goal)
            if hitl_resolved:
                screen_info = ScreenParser.get_screen_summary(self.driver)
            el_count = len(screen_info.get("elements", []))
            ocr_cached = screen_info.get("ocr_cached", False)
            if ocr_cached:
                consecutive_unchanged_screens += 1
                ocr_log = f"⚡ [OCR缓存命中] 屏幕指纹高度一致，0 耗时复用视觉元素 ({el_count} 个)"
                ocr_action = "OCR 缓存复用"
            else:
                consecutive_unchanged_screens = 0
                ocr_log = f"视觉 OCR 成功提取屏幕文字元素: {el_count} 个"
                ocr_action = "OCR 解析完成"

            # 🛡️ 智能防死锁与设备自学习诊断 (Anti-Deadlock & Self-Learning)
            if consecutive_unchanged_screens >= 3:
                logger.warning(f"⚠️ 检测到连续 {consecutive_unchanged_screens} 次操作后真机屏幕完全无响应，启动设备自学习故障诊断...")
                try:
                    from core.device_knowledge_manager import device_knowledge_mgr
                    dev_id = getattr(self.driver, "device_id", None)
                    dev_info = device_knowledge_mgr.get_device_fingerprint(dev_id or "")

                    # 抓取最近底层 logcat
                    res_log = subprocess.run([device_knowledge_mgr.adb_bin, "-s", dev_id, "logcat", "-d", "-t", "40"], capture_output=True, text=True, timeout=3) if dev_id else None
                    log_text = res_log.stdout if res_log else ""

                    # 优先匹配已知机型知识，无记录则 AI 自动学习并保存
                    diag = device_knowledge_mgr.match_knowledge(dev_info, log_text)
                    if not diag:
                        diag = device_knowledge_mgr.learn_and_save_issue(dev_info, "连续多次执行点击/滑动后真机屏幕完全无变动响应", log_text)

                    final_block_reason = f"【{dev_info.get('brand')} {dev_info.get('model')}】{diag.get('title')}：{diag.get('situation')}\n👉 建议排查操作：{diag.get('solution')}"
                    logger.error(f"❌ [设备自学习阻断]\n{final_block_reason}")

                    self._notify_status({
                        "step": step_count,
                        "action": "自学习诊断阻断",
                        "log": f"❌ {final_block_reason}"
                    })
                    break
                except Exception as ex:
                    logger.warning(f"自学习诊断流程执行异常: {ex}")
                    break

            self._notify_status({
                "step": step_count,
                "action": ocr_action,
                "log": ocr_log
            })

            # 第一步进行上下文自愈探测
            if step_count == 1:
                self._ensure_home_context_if_needed(goal, screen_info)
            # 🛡️ 前置登录拦截自愈 (Login Barrier Auto-Healing)
            login_keywords = ["手机号登录", "快捷登录", "密码登录", "微信一键登录", "注册/登录", "未登录", "请先登录"]
            texts_on_screen = [e.get("text", "") for e in screen_info.get("elements", [])]
            is_login_barrier = any(any(kw in t for kw in login_keywords) for t in texts_on_screen)
            if is_login_barrier and not any(k in goal for k in ["登录", "注册"]):
                logger.info("🛡️ [前置自愈] 检测到未登录拦截弹窗，触发免密/测试白名单极速放行流程...")
                self._notify_status({
                    "step": step_count,
                    "action": "登录拦截自愈",
                    "log": "🛡️ 检测到系统未登录拦截弹窗，自动执行勾选协议并填充白名单测试号放行..."
                })
                # 尝试点击协议勾选
                for el in screen_info.get("elements", []):
                    t = el.get("text", "")
                    if any(p in t for p in ["已阅读", "同意", "协议", "隐私"]):
                        self.executor._locate_and_click(el, None)
                        time.sleep(0.3)
                        break
                # 尝试点击一键登录或快速放行按钮
                for el in screen_info.get("elements", []):
                    t = el.get("text", "")
                    if any(p in t for p in ["一键登录", "本机号码", "立即登录", "登录"]):
                        self.executor._locate_and_click(el, None)
                        time.sleep(1.0)
                        break
                screen_info = ScreenParser.get_screen_summary(self.driver)

                # 重新获取一次
                screen_info = ScreenParser.get_screen_summary(self.driver)

            # 检测是否陷入上下滑动震荡循环 (Anti-Oscillation Guard)
            recent_swipes = [h.get("action") for h in self.executor.action_history[-3:] if h.get("action") == "swipe"]
            oscillation_warning = ""
            if len(recent_swipes) >= 2:
                oscillation_warning = """
⚠️【系统防震荡自愈警示】：
检测到你在最近几步内连续多次执行滑动手势，可能已滑过头或陷入了上下震荡死锁！
1. 请仔细核查当前屏幕最下方的元素列表中是否已有提交/发布/确定按钮；
2. 若已识别出提交类按钮，请立即执行 tap 点击！严禁再次盲目执行 swipe；
3. 若元素列表中未提取出文字，长表单的提交按钮通常固定在屏幕正下方悬浮操作条，可直接点击底部 [540, 2150] 附近区域触发提交校验！
"""

            # 2. 构造 Prompt（深度注入目标应用元数据，确保模型知晓测试对象）
            app_context_lines = []
            if self.app_info.get('label'):
                app_context_lines.append(f"- 应用名称: {self.app_info['label']}")
            if self.app_info.get('package'):
                app_context_lines.append(f"- 应用包名: {self.app_info['package']}")
            if self.app_identifier:
                app_context_lines.append(f"- 目标安装包: {self.app_identifier}")
            app_context_str = "\n".join(app_context_lines) if app_context_lines else "- 未指定特定安装包（直接操作当前前台应用）"

            user_prompt = f"""
【待测目标应用】
{app_context_str}

【用户测试总目标】
{goal}

【当前已执行的操作历史】
{json.dumps([{'action': h.get('action'), 'reason': h.get('reason'), 'error': h.get('error')} for h in self.executor.action_history[-4:]], ensure_ascii=False)}
{oscillation_warning}
【当前屏幕可交互元素列表】
{screen_info['element_summary_text']}{lessons_context}

请分析当前界面，并给出你的下一步测试动作决策（纯 JSON）。
"""
            # 3. 大模型决策（支持传入当前截屏进行多模态视觉理解）
            self._notify_status({
                "step": step_count,
                "action": "AI 意图推演",
                "log": f"AI 模型 ({self.llm.model_name}) 正在结合视觉感知分析界面并规划下一步..."
            })
            try:
                # 🛡️ 步骤级弹窗感知与自愈小闭环 (Step Healing)
                dialog_keywords = ["我知道了", "稍后再说", "暂不升级", "残忍拒绝", "跳过", "以后再说"]
                found_dismiss_el = None
                for el in screen_info.get("elements", []):
                    t_clean = (el.get("text") or el.get("content_desc") or "").strip()
                    if any(kw == t_clean for kw in dialog_keywords):
                        found_dismiss_el = el
                        break
                if found_dismiss_el and step_count > 1 and not any(kw in goal for kw in ["升级", "取消", "跳过"]):
                    d_text = found_dismiss_el.get("text") or found_dismiss_el.get("content_desc") or "遮罩"
                    logger.info(f"🛡️ [步骤自愈] 探测到界面临时遮罩浮层【{d_text}】，派发轻量关闭手势原地恢复...")
                    self.executor.tap_element(found_dismiss_el)
                    time.sleep(1.0)
                    screen_info = ScreenParser.get_screen_summary(self.driver)

                decision = self.llm.chat_decision(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    image_base64=screen_info["image_b64"],
                    memory_context=memory_context
                )
                thought = decision.get('thought', '')
                logger.info(f"AI 决策: {thought}")
                self._notify_status({
                    "step": step_count,
                    "action": f"决策: {decision.get('action')}",
                    "thought": thought,
                    "reason": decision.get('reason', ''),
                    "log": f"AI 决策 [{decision.get('action')}]: {thought}"
                })
            except Exception as e:
                err_msg = str(e)
                logger.error(f"❌ 模型决策异常: {err_msg}")
                final_block_reason = f"大模型决策调用异常: {err_msg}"
                self._notify_status({
                    "step": step_count,
                    "action": "决策异常",
                    "log": f"❌ 模型决策异常: {err_msg}"
                })
                break

            # 4. 🚀 借鉴 DeepSeek Harness (DSH)：通过独立 TaskVerifier 门禁审查 finish 请求
            if decision.get("action") == "finish":
                is_valid, verifier_msg, barrier_info = TaskVerifier.verify_finish_claim(
                    goal=goal,
                    screen_info=screen_info,
                    model_thought=thought,
                    model_reason=decision.get("reason", "")
                )
                if not is_valid:
                    logger.warning(f"🛡️ [DSH 核验门禁一票否决]: {verifier_msg}")
                    self._notify_status({
                        "step": step_count,
                        "action": "门禁驳回",
                        "log": f"🛡️ [DSH Verifier 门禁驳回]: {verifier_msg}"
                    })
                    # 强力纠偏：将否决原因作为不可辩驳的事实注入下一轮模型推理上下文
                    self.memory_context.append(f"【系统严格核验门禁一票否决】：你发起的 finish 已被驳回！原因：{verifier_msg}。当前未达成最终目标，严禁擅自宣布成功！请根据界面真实情况继续推进业务或排除阻断！")
                    
                    # 若属于登录阻断，立即触发自动登录注入门禁
                    if barrier_info and barrier_info.get("type") == "LOGIN_BARRIER":
                        resolved = self._check_and_prompt_hitl_credential(screen_info, goal)
                        if resolved:
                            screen_info = ScreenParser.get_screen_summary(self.driver)
                    continue

                # 仅当独立 Verifier 审核通过，才批准完成
                logger.info(f"🎉 目标完成并通过 DSH 独立核验门禁: {decision.get('reason')}")
                self._notify_status({
                    "step": step_count,
                    "action": "完成",
                    "log": f"🎉 测试目标顺利达成 (DSH Verifier 批准通过): {decision.get('reason')}"
                })
                execution_success = True
                break

            # 5. 执行动作并记录轨迹 (内置最多 2 次防抖微重试)
            step_res = self.executor.execute(decision, screen_info["elements"])
            retry_count = 0
            while not step_res.get("success", False) and retry_count < 2 and decision.get("action") not in ["finish", "call_api"]:
                retry_count += 1
                logger.warning(f"🔄 动作执行微重试 ({retry_count}/2)... 重新捕获界面并防抖重试")
                time.sleep(1.0)
                screen_info = ScreenParser.get_screen_summary(self.driver)
                step_res = self.executor.execute(decision, screen_info["elements"])
                if step_res.get("success", False):
                    logger.info("✅ 动作经防抖微重试执行成功！")
                    break
            if not step_res["success"]:
                logger.warning(f"步骤执行失败: {step_res['message']}，将让 AI 在下一步自适应纠偏")
                self._notify_status({
                    "step": step_count,
                    "action": "执行轻微警告",
                    "log": f"⚠️ 步骤执行反馈: {step_res['message']} (AI 将在下一步自适应纠偏)"
                })
            else:
                self._notify_status({
                    "step": step_count,
                    "action": "执行成功",
                    "log": f"✅ 操作完成: {decision.get('reason') or decision.get('action')}"
                })

        logger.info(f"========== 测试结束，共执行 {step_count} 步 ==========")
        return {
            "goal": goal,
            "success": execution_success,
            "total_steps": step_count,
            "error_reason": final_block_reason,
            "history": self.executor.action_history
        }
