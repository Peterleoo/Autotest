import time
import json
import logging
import subprocess
from typing import Optional, List, Dict, Any
from appium import webdriver

from core.llm_client import LLMClient
from core.api_client import APIClient
from ai_engine.screen_parser import ScreenParser, PerceptionMode
from ai_engine.action_executor import ActionExecutor
from core.app_lessons_manager import app_lessons_mgr
from ai_engine.verifier import TaskVerifier

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
10. request_human_help: 唤起人机协同协助（AI 自主发起，杜绝机械死板）。
    - 触发时机：当端侧现实出现 AI 客观上无法自行推导或无法独立完成的实体屏障（例如：真机已下发短信验证码、手机银行/安全令牌、微信扫码授权、图形拼图滑块防刷认证、需要人类指定专属个人业务账号/门店/角色数据）时果断调用。
    - 严禁滥用：若可以通过常规输入测试数据、点击返回或常规页面流转解决的问题，严禁调用该动作！
    - 数据规范：
      {
        "action": "request_human_help",
        "help_type": "input", // 可选: "input" (需要输入信息) | "manual_takeover" (需要投屏手动操作) | "choice" (单选列表)
        "title": "人机协同 · 请输入短信验证码",
        "reason": "当前页面已下发短信验证码，由于验证码发送到用户物理真机SIM卡上，AI无法凭空推导，需要人类协助提供",
        "description": "请查收真机短信并在下方输入验证码：",
        "fields": [
          {
            "key": "sms_code",
            "label": "短信验证码",
            "placeholder": "请输入 4~6 位短信验证码",
            "type": "text",
            "target_index": 5
          }
        ],
        "options": ["选项1", "选项2"], // 仅当 help_type 为 choice 时提供
        "action_button_text": "填入并继续"
      }


🔥 核心决策守则（严格遵守，严禁在 App 内盲目乱跳）：
0. 【DSH 反伪造达成铁律】：
    - 严禁掩耳盗铃！若用户的测试目标要求验证具体业务界面（如：进入房源详情、查看VR、点击咨询弹出咨询窗口、进入个人中心等），而当前真机屏幕仍停留在【登录/注册页、密码输入页、验证码拦截弹窗或网络报错页】，严禁将“拉起了登录拦截/权限控制正常”诡辩为“目标已达成”并调用 finish！
    - 系统配备了独立的 DSH 核验门禁（TaskVerifier），任何在拦截页面擅自调用 finish 的企图都会被一票否决！
    - 若当前处于登录页，优先识别输入框调用 type 注入预设账号密码登录，或点击一键登录放行；只有真正进入目标业务窗口后方可调用 finish！
    - 【严禁捏造虚假登录账号与密码】：遇到任何登录、鉴权、绑定手机号界面时，严禁自行臆造手机号、账号或密码（如 13800138000、123456Aa、admin 等）！必须等待系统凭证自动注入或触发人机协作！擅自伪造凭据将直接判定为用例严重违规！
1. 【界面定性】：在 thought 中第一句必须明确输出：“【当前界面判断】：xxx界面（如：应用手机号登录页/首页推荐/隐私协议弹窗）”。
2. 【目标驱动，严禁乱跳】：
    - 紧扣用户的【测试目标】！不要点击与目标无关的广告或偏门入口。
    - 针对新用户多页引导页/轮播图：严禁每滑一页就停下来重新截屏识别一次！只要定性为引导页，果断直接下发 {"action": "fast_forward_guide", "reason": "新用户引导页极速穿透直达首页"} 或 {"action": "swipe", "direction": "left", "repeat": 3}，一步到位直接翻到最后一页并进入应用首页！
    - 针对长列表浏览：若目标需浏览推荐列表或信息流，可直接使用 repeat 连续滑动（如 {"action": "swipe", "direction": "up", "repeat": 2}），一气呵成减少交互轮次。
    - 针对多轮具身与代词消解（DeepSeek Harness 规范）：若指令中包含“第2个/第2套/第二条/刚才那个”等代词，严格遵照注入的【代词消解】或【活跃列表实体】指示，直接定位并点击该条目或物理坐标，严禁退回桌面或重复重新搜索！
    - 针对登录流程：若有协议勾选先点击协议勾选 -> 点击手机号输入框输入测试号码 -> 点击获取验证码/用密码登录 -> 验证跳转。
    - 针对非首页/误入搜索页自愈铁律：
      若测试目标或当前任务步骤要求在【首页】操作（如“冷启动并穿透至首页”、“点击二手房”、“进入委托服务”、“校验底部Tab导航”等），但当前真机屏幕停留在【搜索页面】（特征：顶部有搜索输入框/右侧有‘取消’文字/页面上有‘历史搜索’或‘热门搜索’）时，严禁原地报错或停滞！第一步必须果断点击【取消】文字（target_index）或下发返回键 {"action": "press_key", "key": "back"}，迅速退回到首页主界面，然后再执行后续首页目标！
    - 针对搜索流程：若当前不在首页（例如误入“委托服务”或“我的”页面），第一步必须先按返回键 {"action": "press_key", "key": "back"} 或点击底部【首页】Tab 回到主页；然后在主页顶部点击搜索框（带有“搜索”或“请输入小区名”）进入搜索页面；在搜索页面，可直接点击下方的【热门搜索】条目（如‘钰龙天下’、‘华润凤凰城’、‘星城国际’）或搜索联想条目，即可一键直达房源搜索结果列表；在房源列表中执行下拉滑动或文本断言（如包含‘万’、‘室’、‘m²’等房源信息），达成目标后果断调用 finish 完成测试！
    - 针对表单录入与必填校验：长表单页面的“免费发布/立即提交”按钮往往固定在屏幕最底部的悬浮操作条（Sticky Bottom Bar）中。严禁在上下滑动中盲目震荡！若表单项已就绪，优先点击页面底部的提交/发布按钮触发必填校验；达成必填校验拦截后，果断调用 finish 完成测试！
    - 针对表单智能推断填充：常规输入框（姓名、手机号、期望售价、租金、面积、小区等），系统内置智能推断引擎，可直接下发 type 动作并给出标准测试值（如手机号 13800138000，姓名 张先生，售价 300，面积 98），系统将秒级合规上屏，严禁停滞等待人工输入！
    - 针对委托服务区：严禁在未要求测试委托服务时点击委托房源或委托卡片！若要求测试委托服务但首页金刚区未看到，优先在金刚区区域执行一次向左滑动手势 (swipe left) 翻页！
3. 【具身闭环与动态任务对齐铁律（核心）】：
    - 思考三部曲：
      ① 现实环境核验：当前真机屏幕实际是什么页面？有哪些关键特征与控件？
      ② 任务可行性判断：对照【当前规划的测试任务清单】，原定当前步骤在眼前现实环境下是否可执行？
      ③ 动作或动态重规划决策：
         - 若可执行，下发物理动作推进；
         - 若现实环境变化、遇到阻碍弹窗、或端侧已直接联动完成后续任务，你必须在 thought 中明确阐明原因，并在 JSON 中提供 "step_progress": <当前已达到的步骤编号，例如 3>，或可选提供 "plan_update": [<调整后的后续步骤数组>]；
    - 严禁机械死板！任务规划必须随时随地随端侧现实演进，保持任务与现实 100% 同步！
4. 【坐标精准感知】：元素列表中附带了视觉 OCR 探测出的屏幕精确物理坐标 [x, y]，你可以直接基于编号或坐标点击。
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
        self._hitl_attempts = 0
        self._last_hitl_signature = None

    def _notify_status(self, data: Dict[str, Any]):
        if self.status_callback:
            try:
                self.status_callback(data)
            except Exception as e:
                logger.warning(f"状态回调异常: {e}")

    def _get_plan_steps_summary(self) -> str:
        """动态获取当前会话的最新任务清单与执行状态"""
        if not self.session_id:
            return ""
        try:
            from pathlib import Path
            sess_file = Path("data/sessions") / f"{self.session_id}.json"
            if not sess_file.exists():
                sess_file = Path("outputs/sessions") / f"{self.session_id}.json"
            if sess_file.exists():
                sess_data = json.loads(sess_file.read_text(encoding="utf-8"))
                steps = sess_data.get("plan_steps", [])
                if steps:
                    lines = ["【当前规划的测试任务清单 (活任务看板)】:"]
                    for idx, st in enumerate(steps, 1):
                        st_name = st.get("title", "")
                        st_desc = st.get("desc", "")
                        st_status = st.get("status", "PENDING")
                        status_zh = "已完成" if st_status in ["COMPLETED", "PASS"] else ("进行中" if st_status == "RUNNING" else "待执行")
                        lines.append(f"  {idx}. [{status_zh}] {st_name} (要求: {st_desc[:28]})")
                    return "\n".join(lines) + "\n\n"
        except Exception:
            pass
        return ""

    def _sync_working_memory(self, screen_info: Dict[str, Any], decision: Optional[Dict[str, Any]] = None):
        """实时同步屏幕实体与最新动作至 Working Memory (Muse 范式)"""
        if not self.session_id:
            return
        try:
            from core.memory_manager import MemoryManager
            from pathlib import Path
            sess_file = Path("data/sessions") / f"{self.session_id}.json"
            if not sess_file.exists():
                sess_file = Path("outputs/sessions") / f"{self.session_id}.json"
            if sess_file.exists():
                sess_data = json.loads(sess_file.read_text(encoding="utf-8"))
                last_act = self.executor.action_history[-1] if self.executor.action_history else None
                MemoryManager.extract_and_update_working_memory(
                    sess_data,
                    screen_info.get("elements", []),
                    last_action=last_act,
                    page_summary=decision.get("thought", "")[:50] if decision else None
                )
                curr_pkg = getattr(self.driver, "current_package", None) or getattr(self.driver, "package_name", None)
                curr_act = getattr(self.driver, "current_activity", None)
                if curr_pkg or curr_act:
                    MemoryManager.update_fact_memory(sess_data, current_package=curr_pkg, current_activity=curr_act)
                sess_file.write_text(json.dumps(sess_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"同步工作记忆跳过: {e}")


    @classmethod
    def _detect_login_screen_state(cls, screen_info: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        根据端侧事实视觉与控件树，深度识别当前登录界面的真实物理状态机分型：
        - "sms_code": 短信验证码已发送，等待填入短信验证码
        - "phone_wait_code": 手机号验证码模式，待填手机号并获取验证码
        - "credential": 传统账号密码登录模式
        - "manual_takeover": 图形滑块拼图/生物识别/复杂人机验证
        """
        elements = screen_info.get("elements", [])
        texts = [e.get("text", "") or e.get("content_desc", "") for e in elements]
        combined = " ".join(texts)

        # 1. 检测图形滑块拼图 / 行为机器人检测
        captcha_keywords = ["按住滑块", "拖动滑块", "拖动下方滑块", "完成拼图", "拖到最右边", "点击倒立文字", "安全验证", "行为验证", "验证码拼图"]
        if any(k in combined for k in captcha_keywords):
            return "manual_takeover", {"reason": "检测到图形滑块拼图或行为验证"}

        # 2. 检测是否处于“短信验证码已发送，等待填入验证码”阶段 (sms_code)
        import re
        has_countdown = bool(re.search(r"重新获取\s*\(?\d+", combined) or re.search(r"\d{1,3}\s*[sS秒]", combined) or any(k in combined for k in ["后重发", "后重新获取", "重新发送("]))
        has_sms_sent_hint = any(k in combined for k in ["验证码已发送", "已发送短信", "短信已发送", "已发送至", "请输入验证码", "请输入短信验证码"])
        
        # 寻找验证码输入控件
        sms_input_el = None
        for el in elements:
            t = (el.get("text") or el.get("content_desc") or "").strip()
            if any(k in t for k in ["请输入验证码", "验证码", "短信验证码"]) and not any(k in t for k in ["获取验证码", "发送验证码", "重新获取", "用验证码登录"]):
                sms_input_el = el
                break

        if (has_countdown or has_sms_sent_hint) and (sms_input_el or any("验证码" in t for t in texts)):
            return "sms_code", {"sms_input_el": sms_input_el, "has_countdown": has_countdown}

        # 3. 检测是否处于“手机号验证码模式（尚未获取验证码）”阶段 (phone_wait_code)
        has_get_code_btn = any(any(k in (el.get("text") or el.get("content_desc") or "") for k in ["获取验证码", "发送验证码"]) for el in elements)
        # 检查是否存在密码输入框
        has_pwd_input = any(any(k in (el.get("text") or el.get("content_desc") or "") for k in ["请输入密码", "密码"]) and not any(k in (el.get("text") or el.get("content_desc") or "") for k in ["用密码登录", "密码登录", "忘记密码", "切换"]) for el in elements)

        if has_get_code_btn and not has_pwd_input:
            return "phone_wait_code", {"has_get_code_btn": True}

        # 4. 账号密码登录
        if has_pwd_input or any(k in combined for k in ["密码登录", "用密码登录", "账号密码登录"]):
            return "credential", {"has_pwd_input": has_pwd_input}

        return "credential", {}

    def _execute_phone_send_sms(self, phone: str, screen_info: Dict[str, Any]) -> bool:
        """
        在手机号验证码登录页面：自动填入手机号 -> 勾选协议 -> 点击获取验证码
        """
        logger.info(f"📱 [手机号验证码流程] 正在自动填入手机号 [{phone}] 并触发获取验证码...")
        self._notify_status({
            "step": getattr(self, "step_count", 0),
            "action": "填手机号并获取验证码",
            "log": f"📱 正在填入测试手机号 [{phone}]，勾选协议并点击【获取验证码】..."
        })
        elements = screen_info.get("elements", [])
        
        # 1. 定位手机号输入框
        phone_el = None
        for el in elements:
            t = (el.get("text") or el.get("content_desc") or "").strip()
            if not any(k in t for k in ["手机号登录", "验证码登录", "密码登录"]):
                if any(k in t for k in ["请输入手机", "手机号", "手机号码", "账号", "登录码"]):
                    phone_el = el
                    break
        if not phone_el:
            edit_texts = [e for e in elements if e.get("is_input") or "EditText" in e.get("class", "")]
            if edit_texts:
                phone_el = edit_texts[0]

        # 2. 定位获取验证码按钮
        get_code_btn = None
        for el in elements:
            t = (el.get("text") or el.get("content_desc") or "").strip()
            if any(k in t for k in ["获取验证码", "发送验证码"]):
                get_code_btn = el
                break

        # 3. 定位协议勾选框
        agree_el = None
        for el in elements:
            t = (el.get("text") or el.get("content_desc") or "").strip()
            if any(k in t for k in ["协议", "同意", "已阅读", "我已阅读"]):
                agree_el = el
                break

        # 执行勾选协议
        if agree_el:
            logger.info("勾选用户与隐私协议")
            try:
                self.executor._locate_and_click(agree_el, None)
                time.sleep(0.3)
            except Exception as e:
                logger.debug(f"勾选协议跳过: {e}")

        # 执行填入手机号
        if phone_el and phone:
            logger.info(f"填入手机号: {phone}")
            self.executor._locate_and_type(phone_el, phone)
            time.sleep(0.4)

        # 点击获取验证码按钮
        if get_code_btn:
            logger.info("点击【获取验证码】按钮")
            self.executor._locate_and_click(get_code_btn, None)
            time.sleep(1.2)
            return True
        else:
            logger.warning("未找到明确的【获取验证码】按钮")
            return False

    def _execute_sms_code_injection(self, sms_code: str, screen_info: Dict[str, Any]) -> bool:
        """
        在短信验证码界面：定位验证码输入框 -> 自动填入验证码 -> 点击登录/提交
        """
        logger.info(f"📨 [短信验证码注入] 正在将短信验证码 [{sms_code}] 自动填入真机...")
        self._notify_status({
            "step": getattr(self, "step_count", 0),
            "action": "填入短信验证码",
            "log": f"📨 正在将短信验证码填入真机输入框并提交登录..."
        })
        elements = screen_info.get("elements", [])

        # 定位验证码输入框
        sms_input_el = None
        for el in elements:
            t = (el.get("text") or el.get("content_desc") or "").strip()
            if any(k in t for k in ["请输入验证码", "验证码", "短信验证码"]) and not any(k in t for k in ["获取验证码", "发送验证码", "重新获取"]):
                sms_input_el = el
                break

        if not sms_input_el:
            edit_texts = [e for e in elements if e.get("is_input") or "EditText" in e.get("class", "")]
            if len(edit_texts) >= 2:
                sms_input_el = edit_texts[1]
            elif edit_texts:
                sms_input_el = edit_texts[0]

        if sms_input_el:
            logger.info(f"定位到验证码输入框: {sms_input_el.get('bounds')}")
            self.executor._locate_and_type(sms_input_el, sms_code)
            time.sleep(0.5)
        else:
            logger.warning("未检出独立验证码输入框，尝试使用原生 ADB 直接输入验证码")
            try:
                self.driver.execute_adb(["shell", "input", "text", sms_code])
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"直接输入验证码失败: {e}")

        # 寻找登录/确定按钮
        login_btn = None
        for el in elements:
            t = (el.get("text") or el.get("content_desc") or "").strip()
            if any(k in t for k in ["登录", "进入", "确定", "完成", "下一步"]):
                if not any(k in t for k in ["密码登录", "切换", "验证码登录", "获取验证码"]):
                    login_btn = el
                    break

        if login_btn:
            logger.info("点击登录提交按钮")
            self.executor._locate_and_click(login_btn, None)
            time.sleep(1.8)
        else:
            logger.info("未检出登录按钮，发送回车键提交")
            try:
                self.driver.press_keycode(66) # KEYCODE_ENTER
                time.sleep(1.5)
            except Exception:
                pass

        try:
            ScreenParser.wait_for_visual_settling(self.driver, max_wait=2.5)
        except Exception:
            time.sleep(1.5)

        # 复核是否跳出登录页
        after_screen = ScreenParser.get_screen_summary(self.driver)
        after_texts = [e.get("text", "") or e.get("content_desc", "") for e in after_screen.get("elements", [])]
        after_combined = " ".join(after_texts)
        is_still_login = any(kw in after_combined for kw in ["手机号登录", "密码登录", "请输入验证码", "重新获取", "获取验证码"])

        if not is_still_login:
            logger.info("🎉 [短信验证码注入] 验证通过：已成功完成登录放行！")
            self._notify_status({
                "step": getattr(self, "step_count", 0),
                "action": "验证码登录完成",
                "log": "✅ 短信验证码提交成功，真机已成功跨过登录拦截，业务链路恢复流转！"
            })
            self._hitl_attempts = 0
            self._last_hitl_signature = None
            return True
        else:
            logger.warning("⚠️ [短信验证码注入] 提交验证码后真机仍停留在当前页，可能验证码错误或需要滑块二次确认")
            return False

    def _execute_credential_injection(self, acc: str, pwd: str, screen_info: Dict[str, Any], goal: str = "") -> bool:
        """
        确定性端侧凭证自动注入流水线 (DSH Credential Injection Pipeline)
        真实模拟用户物理操作：切换密码登录 -> 自动选组织/公司 -> 勾选协议 -> 填手机号/登录码 -> 填密码 -> 提交登录
        """
        logger.info(f"🔑 [DSH 凭证自动注入] 开始对真机执行账号 [{acc}] 真实登录注入流水线 (goal={goal})...")
        self._notify_status({
            "step": 0,
            "action": "自动登录注入",
            "log": f"🔑 正在自动填入测试凭证 [{acc}] 并执行物理登录..."
        })

        elements = screen_info.get("elements", [])

        # 1. 检查是否在验证码登录模式
        # ⚠️ 严苛保护：若测试目标为验证码/短信登录测试，或未提供有效密码，绝对禁止强行切换到密码登录！
        from ai_engine.verifier import TaskVerifier
        is_verify_intent = TaskVerifier.is_testing_auth_or_captcha(goal) or any(k in goal for k in ["验证码", "短信", "机器人检测", "滑块", "防刷"])
        if pwd and not is_verify_intent:
            for el in elements:
                t = (el.get("text") or el.get("content_desc") or "").strip()
                if any(k in t for k in ["用密码登录", "密码登录", "账号密码登录"]):
                    logger.info(f"点击切换到密码登录模式: {t}")
                    self.executor._locate_and_click(el, None)
                    time.sleep(0.6)
                    screen_info = ScreenParser.get_screen_summary(self.driver)
                    elements = screen_info.get("elements", [])
                    break

        # 2. 扫描定位关键组件：手机号/登录码框、密码框、协议框、登录按钮、公司选择框
        phone_el, pwd_el, agree_el, login_btn, company_el = None, None, None, None, None
        edit_texts = []

        for el in elements:
            t = (el.get("text") or el.get("content_desc") or "").strip()
            cls = el.get("class", "")
            is_input = el.get("is_input", False) or "EditText" in cls

            if is_input:
                edit_texts.append(el)

            # 排除页面标题与切换按钮等非输入控件 (例如顶部大标题"手机号登录")
            is_title_or_btn = any(k in t for k in ["手机号登录", "密码登录", "用密码登录", "验证码登录", "立即登录", "快捷登录"])
            if not phone_el and not is_title_or_btn and any(k in t for k in ["请输入手机", "请输入账号", "请输入合伙人", "手机号", "账号", "登录码", "合伙人", "工号"]):
                phone_el = el
            elif not pwd_el and any(k in t for k in ["请输入密码", "密码"]):
                # 排除切换按钮、忘记密码等非输入框文本
                if not any(k in t for k in ["密码登录", "用密码登录", "忘记密码", "切换", "验证码登录"]):
                    pwd_el = el
            elif not agree_el and any(k in t for k in ["协议", "同意", "已阅读", "我已阅读"]):
                agree_el = el
            elif not login_btn and any(k in t for k in ["登录", "进入", "下一步", "同意隐私并下一步"]):
                if not any(k in t for k in ["密码登录", "切换", "验证码登录"]):
                    login_btn = el
            elif not company_el and any(k in t for k in ["请选择您所在的公司", "选择公司", "所属公司"]):
                company_el = el

        # 智能匹配优先：若有明确标记为 is_input 的真实输入框列表
        if edit_texts:
            # 优先在真实输入框中挑选含有手机号/占位符的输入框
            for ed in edit_texts:
                ed_t = (ed.get("text") or ed.get("content_desc") or "").strip()
                if any(k in ed_t for k in ["请输入手机", "手机号", "请输入账号", "账号", "登录码"]):
                    phone_el = ed
                    break
            else:
                if not phone_el:
                    phone_el = edit_texts[0]
                    logger.info(f"使用首个输入框作为账号目标: {phone_el.get('bounds')}")

            if len(edit_texts) >= 2:
                for ed in edit_texts[1:]:
                    ed_t = (ed.get("text") or ed.get("content_desc") or "").strip()
                    if any(k in ed_t for k in ["请输入密码", "密码"]):
                        pwd_el = ed
                        break
                else:
                    if not pwd_el:
                        pwd_el = edit_texts[1]
                        logger.info(f"使用次位输入框作为密码目标: {pwd_el.get('bounds')}")

        # 🛡️ 账号与密码框严格防混淆与互斥校验（杜绝账号与密码被串打入同一个输入框）
        if pwd_el:
            pwd_text = (pwd_el.get("text") or pwd_el.get("content_desc") or "").strip()
            if any(k in pwd_text for k in ["用密码登录", "密码登录", "忘记密码", "切换", "验证码登录"]):
                logger.warning(f"⚠️ 识别到的密码候选元素实为模式切换按钮/链接 [{pwd_text}]，予以剔除")
                pwd_el = None

        if phone_el and pwd_el:
            if phone_el == pwd_el:
                logger.warning("⚠️ 账号与密码候选元素指向同一对象，取消密码输入")
                pwd_el = None
            else:
                p_c = phone_el.get("center")
                w_c = pwd_el.get("center")
                if p_c and w_c:
                    dy = abs(p_c[1] - w_c[1])
                    if dy < 50:
                        logger.warning(f"⚠️ 账号框与密码框垂直间距过小 (dy={dy}px)，判定为同一输入框，禁止填入密码")
                        pwd_el = None

        # 3. 若有公司/组织选择下拉框，尝试轻触展开并选定默认公司
        if company_el:
            logger.info("检测到公司选择下拉框，尝试轻触选定...")
            self.executor._locate_and_click(company_el, None)
            time.sleep(0.6)
            post_company_screen = ScreenParser.get_screen_summary(self.driver)
            # 在弹出的选项中点击包含“象盒”或第一项列表
            for cand in post_company_screen.get("elements", []):
                ct = (cand.get("text") or cand.get("content_desc") or "").strip()
                if any(k in ct for k in ["象盒", "总公司", "测试", "默认", "房产"]):
                    self.executor._locate_and_click(cand, None)
                    logger.info(f"已选中公司组织项: {ct}")
                    time.sleep(0.4)
                    break

        # 4. 执行物理点击协议 (优先点击协议文本左侧勾选框，避免点进隐私条款跳转)
        if agree_el:
            logger.info("勾选服务与隐私协议")
            agree_bounds = agree_el.get("bounds", "")
            checkbox_clicked = False
            for el in elements:
                if el.get("clickable") and el != agree_el:
                    b = el.get("bounds", "")
                    if b and agree_bounds:
                        try:
                            import re
                            m_cb = re.findall(r"\[(\d+),(\d+)\]", b)
                            m_ag = re.findall(r"\[(\d+),(\d+)\]", agree_bounds)
                            if m_cb and m_ag:
                                x2_cb = int(m_cb[1][0])
                                x1_ag = int(m_ag[0][0])
                                y1_cb = int(m_cb[0][1])
                                y1_ag = int(m_ag[0][1])
                                if abs(y1_cb - y1_ag) < 60 and abs(x2_cb - x1_ag) < 80:
                                    self.executor._locate_and_click(el, None)
                                    checkbox_clicked = True
                                    logger.info(f"精准命中协议左侧单选框: {b}")
                                    break
                        except Exception:
                            pass
            if not checkbox_clicked:
                self.executor._locate_and_click(agree_el, None)
            time.sleep(0.3)

        # 5. 执行填入账号
        if phone_el and acc:
            logger.info(f"填入账号/登录码: {acc}")
            self.executor._locate_and_type(phone_el, acc)
            time.sleep(0.4)

        # 6. 执行填入密码 (仅当页面有密码框且用户提供了密码时)
        if pwd_el and pwd:
            logger.info("填入密码: ******")
            self.executor._locate_and_type(pwd_el, pwd)
            time.sleep(0.4)

        # 7. 点击登录提交按钮
        if login_btn:
            logger.info("点击登录提交按钮")
            self.executor._locate_and_click(login_btn, None)
            time.sleep(1.8)
        else:
            logger.info("未明确检出登录按钮，尝试发送回车键提交")
            try:
                self.driver.press_keycode(66) # KEYCODE_ENTER
                time.sleep(1.5)
            except Exception:
                pass

        # 8. 自适应等待画面转场静止
        try:
            ScreenParser.wait_for_visual_settling(self.driver, max_wait=2.5)
        except Exception:
            time.sleep(1.5)

        # 9. 复核是否已成功跳出登录界面
        after_screen = ScreenParser.get_screen_summary(self.driver)
        after_texts = [e.get("text", "") or e.get("content_desc", "") for e in after_screen.get("elements", [])]
        after_combined = " ".join(after_texts)
        is_still_login = any(kw in after_combined for kw in ["手机号登录", "密码登录", "请输入密码", "请输入您的合伙人登录码", "请选择您所在的公司"])

        if not is_still_login:
            logger.info("🎉 [DSH 凭证自动注入] 验证通过：已成功完成登录并跳出鉴权拦截页！")
            self._notify_status({
                "step": 0,
                "action": "登录完成",
                "log": "✅ 测试凭证自动注入完成，真机已成功跨过登录拦截，业务链路恢复流转！"
            })
            self._hitl_attempts = 0
            self._last_hitl_signature = None
            return True
        else:
            logger.warning("⚠️ [DSH 凭证自动注入] 尝试注入后真机仍停留在登录页，可能存在图形滑块验证码、公司未选定或需要手动确认")
            return False

    def _check_and_prompt_hitl_credential(self, screen_info: Dict[str, Any], goal: str) -> bool:
        """
        人机协同登录决策拦截门禁 (Human-in-the-Loop Credential Gate, 对标 DeepSeek Harness 设计)
        若真机界面进入账号密码/验证码/登录码登录页面：
        1. 优先检索当前 App 是否已在设置中心配置预设真实凭证，若有则自动静默注入，保持 100% 无人值守；
        2. 若未配置凭证，立即挂起任务流，向前端发出协同信号唤出【人机协同决策卡片】，AI 推理与步数时钟完全冻结；
        3. 若检测到同界面多次阻断，智能熔断防死循环，自动升级为【投屏手动接管引导】，支持一键放行！
        """
        # 🎯 目标豁免检测 (Goal Immunity Guard):
        # 若当前测试目标明确针对“验证码”、“短信”、“机器人检测”、“滑块验证”、“人机验证”、“图形验证”等，
        # 则当前登录或验证码界面是测试目标本身 (Target under Test)，绝非流程阻断门禁，直接放行给 AI 规划器自主测试！
        from ai_engine.verifier import TaskVerifier
        if TaskVerifier.is_testing_auth_or_captcha(goal):
            logger.info(f"🎯 [受测标的放行] 测试目标针对验证码/安全检测业务流程 ({goal})，跳过鉴权阻断人机协同")
            return False

        texts = [e.get("text", "") or e.get("content_desc", "") for e in screen_info.get("elements", [])]
        combined = " ".join(texts)

        # 识别登录页特征 (多维融合：常见登录关键词 + 合伙人/企业工作台登录码 + 鉴权要素)
        login_keywords = [
            "手机号登录", "密码登录", "账号密码登录", "获取验证码", "请输入手机号码", "请输入手机号", 
            "验证码登录", "立即登录", "快捷登录", "登录码", "合伙人登录", "工号登录", "请選擇您所在的公司", 
            "请选择您所在的公司", "请输入您的合伙人登录码", "同意隐私并下一步", "登录遇到问题"
        ]
        is_login_screen = any(kw in combined for kw in login_keywords)

        if not is_login_screen:
            has_credential_input = any(any(k in (el.get("text") or el.get("content_desc") or "") for k in ["登录码", "账号", "手机号", "工号", "密码"]) for el in screen_info.get("elements", []))
            if has_credential_input and ("登录" in combined or "下一步" in combined or "隐私" in combined or "Sign in" in combined or "Log in" in combined):
                is_login_screen = True
            elif any(kw in goal for kw in ["登录", "账号", "密码", "鉴权"]) and ("登录" in combined or "下一步" in combined or "合伙人" in combined):
                is_login_screen = True

        if not is_login_screen:
            return False

        from core.credential_manager import CredentialManager
        app_key = self.app_identifier or getattr(self.driver, "package_name", None) or "demo_app"
        cred = CredentialManager.get_credential(app_key)
        if not cred and "/" in app_key:
            cred = CredentialManager.get_credential(app_key.split("/")[0])
        if not cred and "." in app_key:
            cred = CredentialManager.get_credential(app_key.split(".")[-1])

        # 1. 深度识别真机登录态分型 (SMS验证码待填 / 手机号待获取验证码 / 账号密码 / 滑块接管)
        login_state, state_meta = self._detect_login_screen_state(screen_info)
        logger.info(f"🔍 [真机登录态识别] 当前登录界面分型为: [{login_state}] (meta={state_meta})")

        # 2. 生成当前屏幕文本特征指纹 (防死循环追踪)
        curr_sig = "|".join(sorted(set(t for t in texts if len(t) >= 2))[:8])
        if self._last_hitl_signature == curr_sig:
            self._hitl_attempts += 1
        else:
            self._hitl_attempts = 1
            self._last_hitl_signature = curr_sig

        session_id = self.session_id or "default_session"

        # 3. 动态自适应协同分支流转
        if login_state == "sms_code":
            # 状态 A: 短信验证码已发送，等待填入短信验证码 -> 精准唤起【短信验证码】人机协同卡片
            logger.info("🛡️ [短信验证码协作] 界面正处于验证码等待输入阶段，唤起【短信验证码】人机协同卡片...")
            print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=sms_code&attempt={self._hitl_attempts}\n", flush=True)
            self._notify_status({
                "step": getattr(self, "step_count", 0),
                "action": "等待短信验证码",
                "log": "⏸️ 短信验证码已发送至测试手机，自动化已安全挂起，请在协同卡片输入短信验证码..."
            })
        elif login_state == "phone_wait_code":
            # 状态 B: 手机号验证码模式（尚未获取验证码）
            if self._hitl_attempts == 1 and cred and cred.get("account"):
                logger.info(f"🔑 [预设手机号生效] 检测到验证码登录页，自动代填手机号 [{cred['account']}] 并点击获取验证码...")
                sent = self._execute_phone_send_sms(cred["account"], screen_info)
                if sent:
                    time.sleep(1.5)
                    new_screen = ScreenParser.get_screen_summary(self.driver)
                    new_state, _ = self._detect_login_screen_state(new_screen)
                    if new_state == "manual_takeover":
                        print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=manual_takeover&attempt={self._hitl_attempts}\n", flush=True)
                        self._notify_status({
                            "step": getattr(self, "step_count", 0),
                            "action": "等待滑块验证",
                            "log": "⏸️ 触发了图形滑块/机器人检测，请直接在右侧真机投屏滑动完成，完成后点击已完成！"
                        })
                    else:
                        print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=sms_code&attempt={self._hitl_attempts}\n", flush=True)
                        self._notify_status({
                            "step": getattr(self, "step_count", 0),
                            "action": "等待短信验证码",
                            "log": f"⏸️ 已自动为您填入手机号 [{cred['account']}] 并点击获取验证码，请查收短信并在下方填入验证码！"
                        })
            else:
                print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=phone_input&attempt={self._hitl_attempts}\n", flush=True)
                self._notify_status({
                    "step": getattr(self, "step_count", 0),
                    "action": "等待手机号输入",
                    "log": "⏸️ 检测到应用处于短信验证码登录页，请输入测试手机号，系统将自动代填并点击获取验证码..."
                })
        elif login_state == "manual_takeover" or self._hitl_attempts >= 2:
            # 状态 C: 滑块/拼图或死循环熔断升级为投屏接管
            logger.warning(f"🛡️ [人机协同手动接管] 界面需滑块拼图或多次阻断 (attempt={self._hitl_attempts})，升级为【投屏手动接管模式】！")
            print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=manual_takeover&attempt={self._hitl_attempts}\n", flush=True)
            self._notify_status({
                "step": getattr(self, "step_count", 0),
                "action": "等待投屏手动完成",
                "log": "⏸️ 端侧检测到需要进一步操作（如滑块拼图/验证码），请直接在右侧真机投屏轻触完成，完成后点击【我已在投屏中完成】！"
            })
        else:
            # 状态 D: 传统账号密码登录
            if self._hitl_attempts == 1 and cred and cred.get("account"):
                injected = self._execute_credential_injection(cred.get("account", ""), cred.get("password", ""), screen_info, goal=goal)
                if injected:
                    return True
            print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=credential&attempt={self._hitl_attempts}\n", flush=True)
            self._notify_status({
                "step": getattr(self, "step_count", 0),
                "action": "人机协同挂起",
                "log": "⏸️ 检测到目标应用进入账号密码登录页，自动化已安全挂起，等待输入凭证或投屏手动登录..."
            })

        from pathlib import Path
        import json
        decision_file = Path(__file__).resolve().parent.parent / "scratch" / f"decision_{session_id}.json"
        if decision_file.exists():
            try: decision_file.unlink()
            except Exception: pass

        # 🚀 对标 DeepSeek Harness: 深度安全挂起（支持长达 1800 秒人工响应，或直到外部终止）
        wait_start = time.time()
        while time.time() - wait_start < 1800:
            if getattr(self, "_stop_requested", False):
                logger.info("🛑 挂起期间收到外部终止指令")
                return False

            if decision_file.exists():
                try:
                    data = json.loads(decision_file.read_text(encoding="utf-8"))
                    if data.get("status") in ["CANCELLED", "STOPPED"] or data.get("decision_type") in ["cancel", "stop", "abort"]:
                        logger.info("🛑 [人机协同响应] 收到用户终止指令，立即退出人机协同等待")
                        try: decision_file.unlink()
                        except Exception: pass
                        return False
                    if data.get("status") == "RESOLVED":
                        decision_type = data.get("decision_type", "inject")
                        logger.info(f"✅ [人机协同响应] 收到用户人工决策: {decision_type}，开始解除挂起...")
                        
                        sms_val = data.get("sms_code", "").strip()
                        acc_val = data.get("account", "").strip()
                        pwd_val = data.get("password", "").strip()

                        if decision_type == "inject_sms" or (sms_val and not pwd_val):
                            injected = self._execute_sms_code_injection(sms_val, screen_info)
                            if injected:
                                self._hitl_attempts = 0
                                self._last_hitl_signature = None
                            else:
                                self._hitl_attempts = max(self._hitl_attempts, 2)
                        elif decision_type == "inject_phone":
                            if acc_val:
                                self._execute_phone_send_sms(acc_val, screen_info)
                                time.sleep(1.5)
                                post_screen = ScreenParser.get_screen_summary(self.driver)
                                post_state, _ = self._detect_login_screen_state(post_screen)
                                if post_state == "manual_takeover":
                                    print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=manual_takeover&attempt=1\n", flush=True)
                                else:
                                    print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=sms_code&attempt=1\n", flush=True)
                        elif decision_type == "inject":
                            if sms_val:
                                self._execute_sms_code_injection(sms_val, screen_info)
                            elif acc_val:
                                injected = self._execute_credential_injection(acc_val, pwd_val, screen_info, goal=goal)
                                if injected:
                                    self._hitl_attempts = 0
                                    self._last_hitl_signature = None
                                else:
                                    self._hitl_attempts = max(self._hitl_attempts, 2)
                        elif decision_type == "manual_done":
                            logger.info("✅ 用户已在投屏手动完成登录，重置人机协同计数器并恢复自动化")
                            self._hitl_attempts = 0
                            self._last_hitl_signature = None
                            time.sleep(1.0)
                        elif decision_type == "skip":
                            logger.info("⏩ 用户选择跳过登录，模拟返回键继续")
                            try: self.driver.back()
                            except Exception: pass
                            time.sleep(1.0)

                        try: decision_file.unlink()
                        except Exception: pass
                        return True
                except Exception as e:
                    logger.warning(f"读取人机协同决策文件异常: {e}")
            time.sleep(1.0)

        logger.warning("⚠️ 等待人机协同超时 (1800s)，安全退出挂起")
        return False

    def _handle_ai_requested_human_help(self, decision: Dict[str, Any], screen_info: Dict[str, Any], goal: str) -> bool:
        """
        处理由 AI 模型根据真机视觉现场自主动态生成的协同请求 (AI-Generated Dynamic HITL Engine)
        """
        title = decision.get("title") or "人机协同 · 需要人工协助"
        reason = decision.get("reason") or decision.get("thought") or "AI 在当前真机界面遇到现实屏障，需要人类协助"
        desc = decision.get("description") or reason
        help_type = decision.get("help_type") or "input"
        fields = decision.get("fields") or []
        options = decision.get("options") or []
        action_btn_text = decision.get("action_button_text") or "提交并继续"
        
        session_id = self.session_id or "default_session"
        app_key = self.app_identifier or getattr(self.driver, "package_name", None) or "demo_app"

        logger.info(f"🤝 [AI 自主发起协同] 类型: {help_type} | 标题: {title} | 原因: {reason}")
        
        # 组装结构化动态 payload
        hitl_payload = {
            "type": "ai_generated",
            "help_type": help_type,
            "mode": "ai_generated",
            "title": title,
            "desc": desc,
            "reason": reason,
            "fields": fields,
            "options": options,
            "action_button_text": action_btn_text,
            "app_key": app_key,
            "timestamp": time.time()
        }

        # 通过持久化会话同步到前端
        from pathlib import Path
        import json
        sess_file = Path("data/sessions") / f"{session_id}.json"
        if not sess_file.exists():
            sess_file = Path("outputs/sessions") / f"{session_id}.json"
        if sess_file.exists():
            try:
                s_data = json.loads(sess_file.read_text(encoding="utf-8"))
                s_data["status"] = "WAITING_USER_INPUT"
                s_data["hitl_decision"] = hitl_payload
                sess_file.write_text(json.dumps(s_data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"更新会话 HITL 状态异常: {e}")

        # 发出控制台事件供 task_manager 实时捕获
        print(f"\n⏸️ [WAIT_HITL_DECISION] session_id={session_id}&app={app_key}&mode=ai_generated&help_type={help_type}\n", flush=True)
        self._notify_status({
            "step": getattr(self, "step_count", 0),
            "action": f"人机协同 ({help_type})",
            "log": f"⏸️ {title}：{reason}"
        })

        decision_file = Path(__file__).resolve().parent.parent / "scratch" / f"decision_{session_id}.json"
        if decision_file.exists():
            try: decision_file.unlink()
            except Exception: pass

        # 深度安全挂起等待人工决策
        wait_start = time.time()
        while time.time() - wait_start < 1800:
            if getattr(self, "_stop_requested", False):
                logger.info("🛑 挂起期间收到外部终止指令")
                return False

            if decision_file.exists():
                try:
                    data = json.loads(decision_file.read_text(encoding="utf-8"))
                    if data.get("status") in ["CANCELLED", "STOPPED"] or data.get("decision_type") in ["cancel", "stop", "abort"]:
                        logger.info("🛑 [AI 协同响应] 收到用户终止指令，立即退出协同等待")
                        try: decision_file.unlink()
                        except Exception: pass
                        return False
                    if data.get("status") == "RESOLVED":
                        logger.info(f"✅ [AI 协同响应] 收到人工提交响应数据: {data}")
                        decision_type = data.get("decision_type", "submit")
                        
                        if decision_type == "manual_done":
                            logger.info("✅ 用户已在投屏手动完成操作，继续自动化")
                            time.sleep(1.0)
                        elif decision_type == "skip":
                            logger.info("⏩ 用户选择跳过该步骤")
                            try: self.driver.back()
                            except Exception: pass
                        else:
                            # 提取用户提交的动态字段数据并自动映射上屏
                            inputs = data.get("inputs") or {}
                            for k, v in data.items():
                                if k not in ["status", "decision_type", "remember", "app_key"] and k not in inputs:
                                    inputs[k] = v

                            for f in fields:
                                f_key = f.get("key")
                                val = str(inputs.get(f_key, "")).strip()
                                if not val and f_key == "sms_code" and "sms_code" in inputs:
                                    val = str(inputs["sms_code"]).strip()
                                if not val:
                                    continue
                                
                                target_el = None
                                t_idx = f.get("target_index")
                                if t_idx is not None:
                                    for el in screen_info.get("elements", []):
                                        if el.get("index") == t_idx:
                                            target_el = el
                                            break
                                if not target_el:
                                    for el in screen_info.get("elements", []):
                                        el_t = (el.get("text") or el.get("content_desc") or "").strip()
                                        if any(k in el_t for k in [f.get("label", ""), f.get("placeholder", ""), "验证码"]):
                                            target_el = el
                                            break

                                if target_el:
                                    logger.info(f"AI 协同字段 [{f_key}] 自动填入组件: {target_el.get('bounds')}")
                                    self.executor._locate_and_type(target_el, val)
                                    time.sleep(0.4)
                                else:
                                    logger.info(f"未找到目标组件，使用原生 ADB 直接填入字段 [{f_key}]: {val}")
                                    try:
                                        self.driver.execute_adb(["shell", "input", "text", val])
                                        time.sleep(0.4)
                                    except Exception:
                                        pass

                            selected_choice = data.get("choice")
                            if selected_choice:
                                for el in screen_info.get("elements", []):
                                    el_t = (el.get("text") or el.get("content_desc") or "").strip()
                                    if selected_choice in el_t:
                                        logger.info(f"AI 协同点击选择项: {selected_choice}")
                                        self.executor._locate_and_click(el, None)
                                        time.sleep(0.6)
                                        break

                            # 点击登录/提交按钮
                            time.sleep(0.4)
                            for el in screen_info.get("elements", []):
                                el_t = (el.get("text") or el.get("content_desc") or "").strip()
                                if any(k in el_t for k in ["登录", "进入", "确定", "下一步", "完成", "提交"]):
                                    if not any(k in el_t for k in ["手机号登录", "密码登录", "切换", "获取验证码", "验证码登录"]):
                                        logger.info(f"自动点击协同后提交按钮: {el_t}")
                                        self.executor._locate_and_click(el, None)
                                        time.sleep(1.5)
                                        break

                        try: decision_file.unlink()
                        except Exception: pass
                        return True
                except Exception as e:
                    logger.warning(f"读取 AI 协同决策文件异常: {e}")
            time.sleep(1.0)

        logger.warning("⚠️ 等待 AI 人机协同超时 (1800s)")
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
        model_display = getattr(self.llm, "model_name", "default")
        logger.info(f"使用模型提供商: {self.llm.provider} ({model_display})")
        if not getattr(self.llm, "client", None):
            err_msg = f"AI 模型服务未连通: 提供商 [{self.llm.provider}] 客户端初始化失败 ({getattr(self.llm, 'init_error', '') or '未配置有效 API 密钥'})。请在【系统设置 ➔ AI 模型服务】中配置有效的 API Key。"
            logger.error(err_msg)
            self._notify_status({
                "step": 0,
                "max_steps": max_steps,
                "goal": goal,
                "action": "模型未连通",
                "log": err_msg
            })
            return {"success": False, "message": err_msg, "error": err_msg}
        self._notify_status({
            "step": 0,
            "max_steps": max_steps,
            "goal": goal,
            "action": "初始化",
            "log": f"启动测试智能体，模型: {self.llm.provider} ({model_display})"
        })

        step_count = 0
        execution_success = False
        consecutive_unchanged_screens = 0
        final_block_reason = ""
        force_vision = False

        while step_count < max_steps:
            if getattr(self, "_stop_requested", False):
                logger.info("🛑 收到外部主动终止信号，安全退出执行循环")
                break

            # 1. 感知当前真机屏幕与元素 (分层感知三级火箭架构: 原生UI树短路 -> 端侧OCR补齐 -> 视觉模型攻坚)
            screen_info = ScreenParser.get_screen_summary(
                self.driver,
                wait_settling=(step_count > 0),
                skip_ocr_if_rich=True,
                goal=goal,
                force_vision=force_vision
            )
            perception_mode = screen_info.get("perception_mode", PerceptionMode.FULL_VISION)
            el_count = len(screen_info.get("elements", []))

            # 🛡️ 步骤前置：检查并触发人机协同登录凭证门禁 (DeepSeek Harness 步数冻结)
            # 若处于登录拦截状态，安全挂起等待用户决策；挂起期间 step_count 绝不累加
            hitl_resolved = self._check_and_prompt_hitl_credential(screen_info, goal)
            if hitl_resolved:
                # 决策完成恢复后，就地复验屏幕状态
                screen_info = ScreenParser.get_screen_summary(
                    self.driver,
                    skip_ocr_if_rich=True,
                    goal=goal,
                    force_vision=force_vision
                )
                perception_mode = screen_info.get("perception_mode", PerceptionMode.FULL_VISION)
                el_count = len(screen_info.get("elements", []))

            # 只有离开阻断状态后，才正式递增有效探索步骤
            step_count += 1
            # 实时沉淀当前真机屏幕实体与工作记忆 (Muse 范式)
            self._sync_working_memory(screen_info)
            logger.info(f"\n--- [Step {step_count}/{max_steps}] 感知界面与决策 ---")

            # 📢 分层感知动态标记与状态上报
            if perception_mode == PerceptionMode.HIERARCHY_TEXT:
                perception_log = f"⚡ [分层感知·极速短路] 原生UI树信息充沛({el_count}个控件)，跳过视觉图片上传，采用纯文本毫秒级决策"
                perception_action = "UI树纯文本短路"
            elif perception_mode == PerceptionMode.OCR_TEXT:
                perception_log = f"📝 [分层感知·OCR补齐] 原生UI树稀疏，端侧本地OCR成功补齐文字({el_count}个控件)，采用轻量纯文本决策"
                perception_action = "OCR纯文本决策"
            else:
                perception_log = f"👁️ [分层感知·视觉攻坚] 检测到自绘/图形界面或升格攻坚，启用多模态视觉模型"
                perception_action = "多模态视觉攻坚"

            logger.info(perception_log)
            self._notify_status({
                "step": step_count,
                "max_steps": max_steps,
                "action": perception_action,
                "log": f"--- [Step {step_count}/{max_steps}] {perception_log} ---"
            })

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

            # 动态检测用户目标是否命中 Working Memory 代词消解 (Muse 槽位继承)
            coref_hint = ""
            if self.session_id:
                try:
                    from core.memory_manager import MemoryManager
                    from pathlib import Path
                    sess_file = Path("data/sessions") / f"{self.session_id}.json"
                    if not sess_file.exists():
                        sess_file = Path("outputs/sessions") / f"{self.session_id}.json"
                    if sess_file.exists():
                        sess_data = json.loads(sess_file.read_text(encoding="utf-8"))
                        hint = MemoryManager.resolve_coreference(goal, sess_data)
                        if hint:
                            coref_hint = f"\n{hint}\n"
                except Exception:
                    pass

            plan_steps_summary = self._get_plan_steps_summary()
            user_prompt = f"""
【待测目标应用】
{app_context_str}

【用户测试总目标】
{goal}{coref_hint}

{plan_steps_summary}

【当前已执行的操作历史】
{json.dumps([{'action': h.get('action'), 'reason': h.get('reason'), 'error': h.get('error')} for h in self.executor.action_history[-4:]], ensure_ascii=False)}
{oscillation_warning}
【当前屏幕可交互元素列表】
{screen_info['element_summary_text']}{lessons_context}

请分析当前界面，并给出你的下一步测试动作决策（纯 JSON）。
"""
            # 3. 大模型决策（分层感知：若为 HIERARCHY_TEXT 或 OCR_TEXT，只传结构化元素树文本；FULL_VISION 传原图）
            image_to_send = screen_info["image_b64"] if perception_mode == PerceptionMode.FULL_VISION else None
            thought_desc = "以纯文本极速模式分析界面" if image_to_send is None else "结合多模态视觉感知分析界面"
            self._notify_status({
                "step": step_count,
                "action": "AI 意图推演",
                "log": f"AI 模型 ({self.llm.model_name}) 正在{thought_desc}并规划下一步..."
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
                    screen_info = ScreenParser.get_screen_summary(
                        self.driver,
                        skip_ocr_if_rich=True,
                        goal=goal,
                        force_vision=force_vision
                    )
                    image_to_send = screen_info["image_b64"] if screen_info.get("perception_mode") == PerceptionMode.FULL_VISION else None

                decision = self.llm.chat_decision(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    image_base64=image_to_send,
                    memory_context=memory_context
                )
                thought = decision.get('thought', '')
                logger.info(f"AI 决策: {thought}")
                step_prog = decision.get('step_progress')
                if step_prog:
                    logger.info(f"📋 [STEP_PROGRESS]: advance_to={step_prog}")
                plan_update = decision.get('plan_update')
                if plan_update and isinstance(plan_update, list):
                    logger.info(f"📋 [PLAN_UPDATE]: {json.dumps(plan_update, ensure_ascii=False)}")
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
                # 若纯文本模式报错，且尚未升级视觉，先尝试升级到视觉攻坚重试该步
                if image_to_send is None and not force_vision:
                    logger.warning(f"⚠️ 纯文本决策遇到异常 ({err_msg})，自动升格到 FULL_VISION 视觉模型攻坚重试...")
                    force_vision = True
                    continue
                final_block_reason = f"大模型决策调用异常: {err_msg}"
                self._notify_status({
                    "step": step_count,
                    "action": "决策异常",
                    "log": f"❌ 模型决策异常: {err_msg}"
                })
                break

            # 🚀 AI 自主发起的人机协同请求 (AI-Generated Dynamic HITL)
            if decision.get("action") == "request_human_help":
                resolved = self._handle_ai_requested_human_help(decision, screen_info, goal)
                if resolved:
                    screen_info = ScreenParser.get_screen_summary(
                        self.driver,
                        skip_ocr_if_rich=True,
                        goal=goal,
                        force_vision=force_vision
                    )
                continue

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
                    # 门禁驳回后强制下一步启用视觉，让 AI 仔细核验界面
                    force_vision = True
                    self._notify_status({
                        "step": step_count,
                        "action": "门禁驳回",
                        "log": f"🛡️ [DSH Verifier 门禁驳回]: {verifier_msg}"
                    })
                    # 强力纠偏：将否决原因作为不可辩驳的事实注入下一轮模型推理上下文
                    if not hasattr(self, "memory_context") or not isinstance(self.memory_context, list):
                        self.memory_context = []
                    self.memory_context.append(f"【系统严格核验门禁一票否决】：你发起的 finish 已被驳回！原因：{verifier_msg}。当前未达成最终目标，严禁擅自宣布成功！请根据界面真实情况继续推进业务或排除阻断！")
                    
                    # 若属于登录阻断，立即触发自动登录注入门禁
                    if barrier_info and barrier_info.get("type") == "LOGIN_BARRIER":
                        resolved = self._check_and_prompt_hitl_credential(screen_info, goal)
                        if resolved:
                            screen_info = ScreenParser.get_screen_summary(
                                self.driver,
                                skip_ocr_if_rich=True,
                                goal=goal,
                                force_vision=force_vision
                            )
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
                screen_info = ScreenParser.get_screen_summary(
                    self.driver,
                    skip_ocr_if_rich=True,
                    goal=goal,
                    force_vision=force_vision
                )
                step_res = self.executor.execute(decision, screen_info["elements"])
                if step_res.get("success", False):
                    logger.info("✅ 动作经防抖微重试执行成功！")
                    break
            if not step_res["success"]:
                logger.warning(f"步骤执行失败: {step_res['message']}，将让 AI 在下一步自适应纠偏并启用视觉攻坚")
                force_vision = True
                self._notify_status({
                    "step": step_count,
                    "action": "执行轻微警告",
                    "log": f"⚠️ 步骤执行反馈: {step_res['message']} (AI 将在下一步启用视觉多模态攻坚自适应纠偏)"
                })
            else:
                # 动作执行成功后，恢复常规分层感知自适应
                force_vision = False
                self._notify_status({
                    "step": step_count,
                    "action": "执行成功",
                    "log": f"✅ 操作完成: {decision.get('reason') or decision.get('action')}"
                })
            # 动作执行后及时固化最新物理锚点与界面状态 (Working Memory)
            self._sync_working_memory(screen_info, decision)

        logger.info(f"========== 测试结束，共执行 {step_count} 步 ==========")
        return {
            "goal": goal,
            "success": execution_success,
            "total_steps": step_count,
            "error_reason": final_block_reason,
            "history": self.executor.action_history
        }
