import json
import logging
import subprocess
from typing import Optional, List, Dict, Any
from appium import webdriver

from core.llm_client import LLMClient
from core.api_client import APIClient
from ai_engine.screen_parser import ScreenParser
from ai_engine.action_executor import ActionExecutor

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
1. 【界面定性】：在 thought 中第一句必须明确输出：“【当前界面判断】：xxx界面（如：象盒找房手机号登录页/首页推荐/隐私协议弹窗）”。
2. 【目标驱动，严禁乱跳】：
    - 紧扣用户的【测试目标】！不要点击与目标无关的广告或偏门入口。
    - 针对新用户多页引导页/轮播图：严禁每滑一页就停下来重新截屏识别一次！只要定性为引导页，果断直接下发 {"action": "fast_forward_guide", "reason": "新用户引导页极速穿透直达首页"} 或 {"action": "swipe", "direction": "left", "repeat": 3}，一步到位直接翻到最后一页并进入应用首页！
    - 针对长列表浏览：若目标需浏览推荐列表或信息流，可直接使用 repeat 连续滑动（如 {"action": "swipe", "direction": "up", "repeat": 2}），一气呵成减少交互轮次。
    - 针对登录流程：若有协议勾选先点击协议勾选 -> 点击手机号输入框输入测试号码 -> 点击获取验证码/用密码登录 -> 验证跳转。
    - 针对搜索流程：若当前不在首页（例如误入“委托服务”或“我的”页面），第一步必须先按返回键 {"action": "press_key", "key": "back"} 或点击底部【首页】Tab 回到主页；然后在主页顶部点击搜索框（带有“搜索”或“请输入小区名”）进入搜索页面；在搜索页面，可直接点击下方的【热门搜索】条目（如‘钰龙天下’、‘华润凤凰城’、‘星城国际’）或搜索联想条目，即可一键直达房源搜索结果列表；在房源列表中执行下拉滑动或文本断言（如包含‘万’、‘室’、‘m²’等房源信息），达成目标后果断调用 finish 完成测试！
    - 针对表单录入与必填校验：长表单页面的“免费发布/立即提交”按钮往往固定在屏幕最底部的悬浮操作条（Sticky Bottom Bar）中。严禁在上下滑动中盲目震荡！若表单项已就绪，优先点击页面底部的提交/发布按钮触发必填校验；达成必填校验拦截后，果断调用 finish 完成测试！
    - 针对委托服务区：严禁在未要求测试委托服务时点击委托房源或委托卡片！
3. 【坐标精准感知】：元素列表中附带了视觉 OCR 探测出的屏幕精确物理坐标 [x, y]，你可以直接基于编号或坐标点击。
4. 【禁止无意义刷步与盲目滑动】：严禁原地重复上下滑动；达成业务目标后应果断调用 finish 完成测试。
5. 输出格式必须是纯 JSON，不要包含任何 markdown 代码块包裹或解释文本。

JSON 输出格式样例：
{
  "thought": "【当前界面判断】：象盒找房登录授权界面。当前页面有手机号输入框[编号5]和隐私协议[编号10]，先点击勾选隐私政策协议。",
  "action": "tap",
  "target_index": 10,
  "reason": "勾选同意用户服务与隐私协议"
}
"""

class AITestAgent:
    """
    AI 驱动测试智能体：零门槛驱动移动端交互、功能及接口测试
    """
    def __init__(self, driver: webdriver.Remote, llm_provider: Optional[str] = None, status_callback: Optional[Any] = None):
        self.driver = driver
        self.llm = LLMClient(provider=llm_provider)
        self.api_client = APIClient()
        self.executor = ActionExecutor(driver=self.driver, api_client=self.api_client)
        self.status_callback = status_callback

    def _notify_status(self, data: Dict[str, Any]):
        if self.status_callback:
            try:
                self.status_callback(data)
            except Exception as e:
                logger.warning(f"状态回调异常: {e}")

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
                    "log": "🛡️ 检测到当前滞留在委托服务二级页面，自动按返回键归位至象盒找房首页"
                })
                try:
                    self.driver.back()
                    import time; time.sleep(1.0)
                except Exception:
                    pass

    def run_goal(self, goal: str, max_steps: int = 15) -> Dict[str, Any]:
        """
        根据自然语言目标执行自动化测试主循环
        """
        logger.info(f"========== 开始 AI 驱动自动化测试 ==========")
        logger.info(f"目标: {goal}")
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

            # 2. 构造 Prompt
            user_prompt = f"""
【用户测试总目标】
{goal}

【当前已执行的操作历史】
{json.dumps([{'action': h.get('action'), 'reason': h.get('reason'), 'error': h.get('error')} for h in self.executor.action_history[-4:]], ensure_ascii=False)}
{oscillation_warning}
【当前屏幕可交互元素列表】
{screen_info['element_summary_text']}

请分析当前界面，并给出你的下一步测试动作决策（纯 JSON）。
"""
            # 3. 大模型决策（支持传入当前截屏进行多模态视觉理解）
            self._notify_status({
                "step": step_count,
                "action": "AI 意图推演",
                "log": f"AI 模型 ({self.llm.model_name}) 正在结合视觉感知分析界面并规划下一步..."
            })
            try:
                decision = self.llm.chat_decision(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    image_base64=screen_info["image_b64"]
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
                logger.error(f"模型决策异常: {e}")
                self._notify_status({
                    "step": step_count,
                    "action": "决策异常",
                    "log": f"❌ 模型决策异常: {e}"
                })
                break

            # 4. 判断是否完成
            if decision.get("action") == "finish":
                logger.info(f"🎉 目标完成: {decision.get('reason')}")
                self._notify_status({
                    "step": step_count,
                    "action": "完成",
                    "log": f"🎉 测试目标顺利达成: {decision.get('reason')}"
                })
                execution_success = True
                break

            # 5. 执行动作并记录轨迹
            step_res = self.executor.execute(decision, screen_info["elements"])
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
