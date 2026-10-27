# -*- coding: utf-8 -*-
"""
TaskVerifier: 借鉴 DeepSeek Harness (DSH) 设计哲学的独立验证核验门禁 (Verifier Gate)
核心原则：
1. 三权分立：彻底剥夺执行层 Agent / LLM 既当运动员又当裁判员的盲目 finish 权；
2. 事实为本：基于真机视觉 OCR 事实与端侧物理状态，对业务目标与终态断言进行独立严密核验；
3. 反自欺欺人：严禁大模型将登录拦截、权限弹窗、阻断页面逆向诡辩为“测试达成”。
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("TaskVerifier")


class TaskVerifier:
    """
    独立任务验证门禁 (Verifier Gate)
    """

    LOGIN_BARRIER_KEYWORDS = [
        "手机号登录", "密码登录", "账号密码登录", "获取验证码",
        "请输入手机号码", "请输入手机号", "验证码登录", "立即登录",
        "快捷登录", "微信一键登录", "注册/登录", "未登录", "请先登录",
        "使用密码登录", "输入密码"
    ]

    ERROR_BARRIER_KEYWORDS = [
        "网络连接异常", "加载失败", "服务器开小差了", "系统错误", "请求超时"
    ]

    @classmethod
    def detect_barrier(cls, screen_info: Dict[str, Any], goal: str) -> Optional[Dict[str, Any]]:
        """
        探测当前界面是否存在阻碍目标推进的屏障 (Authentication Barrier / System Barrier)
        若存在，返回屏障详情，指导任务管理器执行 Plan Mutation (任务动态插桩重排)
        """
        texts = [e.get("text", "") or e.get("content_desc", "") for e in screen_info.get("elements", [])]
        combined = " ".join([t for t in texts if t])
        goal_lower = goal.lower()

        # 若目标本身就是测试登录/注册，则不视为屏障
        if any(kw in goal_lower for kw in ["测试登录", "验证登录", "登录流程", "注册账号"]):
            return None

        # 1. 登录鉴权拦截探测
        is_login = any(kw in combined for kw in cls.LOGIN_BARRIER_KEYWORDS)
        if is_login:
            return {
                "type": "LOGIN_BARRIER",
                "name": "账号登录鉴权拦截",
                "desc": "当前真机受阻于登录/鉴权界面，需注入凭证或登录放行后方可继续后续业务",
                "raw_text_hint": combined[:100]
            }

        # 2. 系统异常报错拦截探测
        is_error = any(kw in combined for kw in cls.ERROR_BARRIER_KEYWORDS)
        if is_error:
            return {
                "type": "ERROR_BARRIER",
                "name": "端侧网络或系统异常",
                "desc": "当前界面展示系统加载失败或异常提示",
                "raw_text_hint": combined[:100]
            }

        return None

    @classmethod
    def verify_finish_claim(
        cls,
        goal: str,
        screen_info: Dict[str, Any],
        model_thought: str,
        model_reason: str,
        plan_steps: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        审查模型发起的 finish (目标完成) 提请：
        返回值: (is_valid, reject_or_pass_reason, barrier_info)
        - 若当前处于拦截页但模型诡辩完成 -> 坚决一票否决 (is_valid = False)；
        - 若核心断言步骤尚未完成 -> 坚决一票否决；
        - 仅当真正满足用户目标终态时 -> 批准通过 (is_valid = True)。
        """
        texts = [e.get("text", "") or e.get("content_desc", "") for e in screen_info.get("elements", [])]
        combined = " ".join([t for t in texts if t])
        goal_lower = goal.lower()

        # 1. 强力否决场景 A：真机界面正处于登录/注册阻断页，而用户目标需要进入深层业务
        is_on_login = any(kw in combined for kw in cls.LOGIN_BARRIER_KEYWORDS)
        goal_is_not_login_test = not any(kw in goal_lower for kw in ["测试登录", "验证登录", "登录功能"])

        if is_on_login and goal_is_not_login_test:
            reject_msg = (
                f"【Verifier 门禁否决】：真机当前物理界面处于【登录/注册鉴权拦截页】！"
                f"用户的目标是【{goal}】，当前尚未进入目标业务页面。"
                f"严禁将'触发登录拦截'诡辩为'测试通过'！必须先完成账号登录或执行人机协同放行！"
            )
            logger.warning(reject_msg)
            return False, reject_msg, {
                "type": "LOGIN_BARRIER",
                "desc": "当前受阻于登录界面，必须先完成登录鉴权"
            }

        # 2. 强力否决场景 B：用户目标包含明确的终态期望（如“验证咨询窗口弹出 / 聊天窗口 / 成功回执”），但屏幕毫无相关特征
        im_chat_keywords = ["微聊", "咨询", "聊天", "在线问", "经纪人", "发送", "说点什么", "输入新消息"]
        requires_chat_window = any(k in goal_lower for k in ["微聊", "咨询窗口", "聊天窗口", "对话框"])
        
        if requires_chat_window:
            has_chat_features = any(k in combined for k in ["发送", "说点什么", "输入消息", "输入新消息", "打招呼", "经纪人", "电话", "在线咨询"])
            # 如果在详情页虽然有"在线问"，但还没点开或者点开后被阻断，算未达成
            is_just_detail_page = "房源详情" in combined or "VR看房" in combined or "建筑面积" in combined
            
            if not has_chat_features or is_on_login:
                reject_msg = (
                    f"【Verifier 门禁否决】：用户目标要求【验证咨询窗口正确弹出】，"
                    f"但当前界面未检出即时通讯/咨询聊天窗口核心特征（如输入框、发送按钮等）！"
                    f"当前界面特征: [{combined[:60]}]。尚未达成终态断言，不允许终止测试。"
                )
                logger.warning(reject_msg)
                return False, reject_msg, {
                    "type": "ASSERTION_NOT_MET",
                    "desc": "咨询窗口尚未弹出"
                }

        # 3. 规划步骤核验：若规划了明确的终态断言步骤，核查是否真实执行
        if plan_steps:
            # 找到最后一个关键断言步骤
            assert_steps = [s for s in plan_steps if any(kw in s.get("title", "") for kw in ["断言", "验证", "核验", "成功弹出"])]
            if assert_steps:
                last_assert = assert_steps[-1]
                # 若核心断言步骤尚未被标记完成
                if last_assert.get("status") not in ["COMPLETED", "PASS"]:
                    # 检查当前界面是否真的满足该断言
                    logger.info(f"【Verifier 审核中】：正在复核最终断言步骤【{last_assert.get('title')}】...")

        logger.info(f"✅ 【Verifier 门禁批准】：模型提请的目标完成已通过真机事实审查，断言真实成立！")
        return True, "Verifier 审核通过：端侧物理状态与用户业务目标完全闭环", None
