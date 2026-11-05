# -*- coding: utf-8 -*-
"""会话创建与多轮对话：创建、审批、桥接轮次、追加消息"""
from core.memory_manager import MemoryManager
import re
import time
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from core.timeline_manager import TimelineManager
from core.task_common import BASE_DIR

logger = logging.getLogger("TaskManager")


class ConversationMixin:
    """会话创建与多轮对话：创建、审批、桥接轮次、追加消息"""

    def create_session(
        self,
        goal: str,
        device_ids: Optional[List[str]] = None,
        test_mode: str = "real",
        case_name: str = "auto_flow",
        approval_mode: str = "auto",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        app_filename: Optional[str] = None,
        app_package: Optional[str] = None,
        app_label: Optional[str] = None,
        app_activity: Optional[str] = None,
        app_id: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        创建一个新任务会话并分发给一个或多个目标设备并发执行，支持自动放行与人工审批确认
        """
        from core.app_manager import AppManager
        app_mgr = AppManager()

        # 若未显式传入设备，则自动探测当前所有在线设备
        if not device_ids:
            conn_devs = app_mgr.get_connected_devices()
            if conn_devs:
                device_ids = [conn_devs[0] if isinstance(conn_devs[0], str) else conn_devs[0].get("id", "auto_device")]
            else:
                raise ValueError("未检测到任何在线可用的物理真机！当前已杜绝免机仿真，请使用 USB 数据线连接手机并开启开发者选项中的【USB 调试】。")

        # 🚀 目标真机独占调度：若目标设备存在未完成旧任务（如 WAITING_USER_INPUT、RUNNING 等），自动抢占并安全终止旧任务
        for dev_id in device_ids:
            for old_sid, old_sess in list(self.sessions.items()):
                if dev_id in old_sess.get("target_devices", []):
                    old_status = old_sess.get("status")
                    if old_status in ["RUNNING", "WAITING_USER_INPUT", "PAUSED", "QUEUED", "AWAITING_APPROVAL"]:
                        logger.info(f"⚡ [设备抢占] 目标真机 [{dev_id}] 存在未完成旧任务 [{old_sid}] (状态: {old_status})，自动接管抢占")
                        self.stop_session(old_sid)

        session_id = f"sess_{datetime.now().strftime('%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        title = goal[:20] + ("..." if len(goal) > 20 else "")
        is_auto = (approval_mode == "auto")
        init_status = "PLANNING" if is_auto else "AWAITING_APPROVAL"

        # 🚀 0ms 极速首包响应：初始轻量思考态，端侧截屏与大模型推演沉降至后台工作线程，告别网络阻塞
        bullets = [
            {"tag": "端侧环境感知与起点确认", "content": "物理真机已在线，正在感知端侧前台状态并推演起跑点..."},
            {"tag": "业务意图推演", "content": f"深度解析测试目标【{goal}】，正在构建最优差量执行路径..."}
        ]
        if attachments:
            doc_att = [a for a in attachments if a.get("is_doc")]
            img_att = [a for a in attachments if a.get("is_image")]
            if doc_att:
                doc_names = "、".join([d.get("name") or d.get("filename", "文档") for d in doc_att])
                bullets.append({"tag": "多模态需求资产对齐", "content": f"已成功挂载需求文档【{doc_names}】，完成测试规约结构化提取"})
            if img_att:
                bullets.append({"tag": "视觉设计参考对齐", "content": f"已载入 {len(img_att)} 张参考设计/缺陷截图，比对端侧页面关键视图特征"})
        bullets.extend([
            {"tag": "入口寻路策略", "content": "动态规划业务核心频道与控件巡航策略..."},
            {"tag": "断言与防抖策略", "content": "制定视图核验与表单响应防抖预案..."}
        ])

        initial_thinking = {
            "duration": "推演中...",
            "bullets": bullets
        }

        init_timeline = [
            TimelineManager.create_user_block(goal, turn_id=0, attachments=attachments),
            TimelineManager.create_thought_block("推演中...", initial_thinking["bullets"], turn_id=0)
        ]

        init_fact = MemoryManager.create_empty_fact_memory()
        init_fact["current_package"] = app_package or ""

        init_turn = {
            "turn_id": 1,
            "user_message": goal,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "thinking": initial_thinking,
            "plan_steps": [],
            "actions": [],
            "conclusion": "",
            "status": init_status,
            "is_rework": False,
            "rework_note": ""
        }

        # 🌟 统一 App 标识符提取规则 (精准对齐待测工程目录，彻底杜绝无序落入 demo_app)
        calc_app_id = app_id
        if not calc_app_id or calc_app_id == "demo_app":
            if app_filename:
                from pathlib import Path
                calc_app_id = Path(app_filename).stem
            elif app_package:
                pkg_str = str(app_package)
                lbl_str = str(app_label or "")
                if "apicloud.A6995433058179" in pkg_str or "象盒找房" in lbl_str:
                    calc_app_id = "xianghe_zhaofang"
                elif "xhj.workbench" in pkg_str or "象盒工作台" in lbl_str:
                    calc_app_id = "xianghe_workbench"
                else:
                    calc_app_id = re.sub(r"[^\w]+", "_", pkg_str).strip("_").lower()
            elif app_label:
                lbl_str = str(app_label)
                if "象盒找房" in lbl_str:
                    calc_app_id = "xianghe_zhaofang"
                elif "象盒工作台" in lbl_str:
                    calc_app_id = "xianghe_workbench"
                else:
                    calc_app_id = re.sub(r"[^\w]+", "_", lbl_str).strip("_").lower()
            else:
                calc_app_id = "demo_app"

        session = {
            "session_id": session_id,
            "title": title,
            "goal": goal,
            "case_name": case_name,
            "test_mode": test_mode,
            "approval_mode": approval_mode,
            "provider": provider,
            "model": model,
            "app_id": calc_app_id,
            "app_filename": app_filename,
            "app_package": app_package,
            "app_label": app_label,
            "app_activity": app_activity,
            "created_at": datetime.now().strftime("%H:%M:%S"),
            "timestamp": time.time(),
            "status": init_status,
            "target_devices": device_ids,
            "thinking": initial_thinking,
            "clarification": None,
            "attachments": attachments or [],
            "messages": [
                {"role": "user", "content": goal, "attachments": attachments or [], "timestamp": datetime.now().strftime("%H:%M:%S")}
            ],
            "turns": [init_turn],
            "fact_memory": init_fact,
            "deliverables": [],
            "rework_history": [],
            "token_stats": {
                "total_tokens": 0,
                "context_window": 1048576,
                "pressure_level": "normal"
            },
            "timeline_blocks": init_timeline,
            "plan_steps": [],
            "devices": {},
            "report_url": "",
            "is_solidified": False,
            "solidified_filename": "",
            "solidified_module": ""
        }

        # 构建各个设备的执行上下文
        for dev_id in device_ids:
            model_label = self._resolve_device_label(dev_id, test_mode)
            platform = "iOS" if "ios" in dev_id.lower() or "iphone" in dev_id.lower() else "Android"
            session["devices"][dev_id] = {
                "device_id": dev_id,
                "model": model_label,
                "platform": platform,
                "status": "QUEUED" if is_auto else "AWAITING_APPROVAL",
                "step": 0,
                "max_steps": 15,
                "action": "端侧情境感知与动态规划中...",
                "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 任务会话已创建，分配设备 [{model_label}]，正在感知端侧意图与情境..."],
                "report_url": "",
                "success": None,
                "duration": "0s",
                "start_time": time.time()
            }

        self.sessions[session_id] = session
        self.active_session_id = session_id
        self._save_session(session_id)

        # 🚀 毫秒级首包即返：端侧情境探测、规划步骤分解与大模型推演全部在后台工作线程并发推进
        def _async_plan_and_dispatch():
            try:
                t_decomp_start = time.time()
                primary_dev = device_ids[0] if device_ids else None
                if not primary_dev:
                    conn_devs = app_mgr.get_connected_devices()
                    if conn_devs:
                        primary_dev = conn_devs[0] if isinstance(conn_devs[0], str) else conn_devs[0].get("id")
                from core.device_context_inspector import DeviceContextInspector
                dev_ctx = DeviceContextInspector.inspect(app_mgr.adb_bin, primary_dev, app_package) if primary_dev else None

                # ------------------------------------------------------------------
                # 🚀 场景 A: 需求文档驱动系统测试套件提炼与串联执行 (Doc-Driven Suite Mode)
                # ------------------------------------------------------------------
                doc_att = [a for a in (attachments or []) if isinstance(a, dict) and a.get("is_doc")]
                is_doc_driven = False
                if doc_att:
                    g_low = goal.lower()
                    doc_kws = ["文档", "用例", "测试用例", "生成", "套件", "prd", "需求", "规约", "写用例", "按照", "系统测试", "业务规格", "测试", "自动测试"]
                    if any(k in g_low for k in doc_kws) or len(goal.strip()) <= 30:
                        is_doc_driven = True

                if is_doc_driven and doc_att:
                    try:
                        doc_entry = doc_att[0]
                        doc_text = doc_entry.get("extracted_text") or ""
                        if not doc_text and doc_entry.get("path"):
                            from pathlib import Path as FilePath
                            fp = FilePath(doc_entry["path"])
                            if fp.exists():
                                doc_text = fp.read_text(encoding="utf-8", errors="ignore")
                        doc_filename = doc_entry.get("name") or doc_entry.get("filename") or "需求规格说明书.md"

                        from core.test_spec_synthesizer import TestSpecSynthesizer

                        cur_sess = self.sessions.get(session_id) or {}

                        # 🛡️ 文档与待测应用业务契合度智能门禁 (Doc-App Relevance Guard)
                        app_disp_name = cur_sess.get("app_label") or cur_sess.get("app_id") or "待测应用"
                        app_pkg = cur_sess.get("app_package") or ""
                        relevance_info = TestSpecSynthesizer.check_doc_app_relevance(
                            doc_text=doc_text,
                            app_name=app_disp_name,
                            app_package=app_pkg,
                            app_label=cur_sess.get("app_label")
                        )

                        is_force = cur_sess.get("force_run_doc_suite", False)
                        if not relevance_info.get("is_relevant") and not is_force:
                            logger.warning(f"🛑 [Doc-App Guard] 拦截到不匹配文档《{doc_filename}》与待测应用【{app_disp_name}】")
                            cur_sess["status"] = "AWAITING_USER_INPUT"
                            guard_block = TimelineManager.create_doc_mismatch_guard_block(
                                session_id=session_id,
                                doc_name=doc_filename,
                                app_name=app_disp_name,
                                relevance_info=relevance_info
                            )
                            tb = cur_sess.setdefault("timeline_blocks", [])
                            # 避免重复插入卡片
                            if not any(b.get("type") == "doc_mismatch_guard" for b in tb):
                                tb.append(guard_block)

                            thought_block = next((b for b in tb if b.get("type") == "thought"), None)
                            if thought_block:
                                thought_block["bullets"] = [
                                    {"tag": "规约与待测应用契合度核验", "content": f"⚠️ 上传文档《{doc_filename}》({relevance_info.get('doc_domain')}) 与当前应用【{app_disp_name}】({relevance_info.get('app_domain')}) 业务域不匹配。"},
                                    {"tag": "执行安全防御拦截", "content": "已安全暂停自动化派发，杜绝真机跨领域无效执行与 Token 浪费，请在下方选择纠偏或切换。"}
                                ]
                            for dev_id in device_ids:
                                if dev_id in cur_sess.get("devices", {}):
                                    cur_sess["devices"][dev_id]["action"] = "文档与应用不匹配，已暂停等待确认"
                                    cur_sess["devices"][dev_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ [门禁拦截] 文档《{doc_filename}》与应用【{app_disp_name}】领域不匹配，已暂停执行并请求人工确认")

                            self._save_session(session_id)
                            return

                        if self._dispatch_doc_suite(session_id, doc_text, doc_filename, provider, model, is_auto, t_decomp_start):
                            return
                    except Exception as err:
                        logger.error(f"需求文档驱动套件提炼异常，降级常规规划: {err}", exc_info=True)

                plan_steps = self._decompose_plan_steps(goal, is_auto, device_context=dev_ctx)
                decomp_dur = round(time.time() - t_decomp_start + 0.35, 2)
                duration_str = f"{decomp_dur}s"

                step_titles = [s["title"] for s in plan_steps]
                key_steps_str = " ➔ ".join(step_titles[:3]) if len(step_titles) >= 2 else "业务流程推进"
                assert_step = next((s["title"] for s in plan_steps if "断言" in s["title"]), "核心业务指标")

                g_low = goal.lower()
                if any(k in g_low for k in ["委托", "卖房", "出租", "放盘"]):
                    nav_strategy = "【业主委托链路】入口寻路推演：1. 优先扫描首页金刚区核心功能位（识别'委托服务/我要卖房'图文控件）；2. 若首屏未检出，降级至底栏【我的】个人中心定位'业主服务/房屋委托'。"
                elif any(k in g_low for k in ["搜索", "二手房", "租房", "新房", "商圈"]):
                    nav_strategy = "【买房/租房检索链路】入口寻路推演：首选首页金刚区核心频道入口，进入列表后通过顶栏搜索框或多维筛选器流转。"
                else:
                    nav_strategy = f"【业务闭环链路】针对【{key_steps_str}】采用页面组件树感知与 OCR 双通道动态寻路。"

                final_thinking = {
                    "duration": duration_str,
                    "bullets": [
                        {"tag": "端侧环境感知与起点确认", "content": dev_ctx.get("planning_hint", "物理真机已在线，结合当前画面按需推演起跑点。") if dev_ctx else "物理真机已在线，结合当前画面按需推演起跑点。"},
                        {"tag": "业务意图推演", "content": f"深度解析测试目标【{goal}】，拆解为 {len(plan_steps)} 个差量业务阶段：{key_steps_str}。"},
                        {"tag": "入口寻路策略", "content": nav_strategy},
                        {"tag": "断言与防抖策略", "content": f"针对【{assert_step}】启用视图状态核验与表单响应防抖，确保字段与校验结果确定性。"}
                    ]
                }

                cur_sess = self.sessions.get(session_id)
                if not cur_sess or cur_sess.get("status") in ["STOPPED", "FAILED"]:
                    return

                cur_sess["thinking"] = final_thinking
                cur_sess["plan_steps"] = plan_steps
                cur_sess["status"] = "RUNNING" if is_auto else "AWAITING_APPROVAL"
                if cur_sess.get("turns"):
                    cur_sess["turns"][0]["thinking"] = final_thinking
                    cur_sess["turns"][0]["plan_steps"] = plan_steps
                    cur_sess["turns"][0]["status"] = cur_sess["status"]

                # 原子更新时间轴块
                tb = cur_sess.setdefault("timeline_blocks", [])
                thought_block = next((b for b in tb if b.get("type") == "thought"), None)
                if thought_block:
                    thought_block["duration"] = duration_str
                    thought_block["bullets"] = final_thinking["bullets"]
                
                # 挂载或更新 todo 块
                todo_block = next((b for b in tb if b.get("type") == "todo_list"), None)
                if not todo_block:
                    tb.append(TimelineManager.create_todo_block(plan_steps, turn_id=0))
                else:
                    todo_block["total_count"] = len(plan_steps)
                    todo_block["title"] = f"任务清单 · 0/{len(plan_steps)} 已完成"
                    todo_block["items"] = [
                        {"title": s["title"], "desc": s.get("desc", ""), "status": s.get("status", "READY"), "diff_type": "added"}
                        for s in plan_steps
                    ]

                for dev_id in device_ids:
                    if dev_id in cur_sess.get("devices", {}):
                        cur_sess["devices"][dev_id]["action"] = "等待自动分发调度..." if is_auto else "等待人工审批确认方案..."

                self._save_session(session_id)

                # 🚀 若为自动放行模式，规划完毕后立即派发设备工作线程并发执行
                if is_auto:
                    for dev_id in device_ids:
                        self.executor.submit(self._device_worker, session_id, dev_id, goal, case_name, test_mode)

                # 🚀 继续在后台异步进行大模型细化富化推演（若开启）
                try:
                    ai_thinking, ai_steps = self._generate_ai_plan_and_thinking(goal, is_auto, test_mode, provider=provider, model=model)
                    c_sess = self.sessions.get(session_id)
                    if c_sess and c_sess.get("status") not in ["STOPPED", "FAILED", "COMPLETED"]:
                        if ai_thinking:
                            c_sess["thinking"] = ai_thinking
                            for b in c_sess.get("timeline_blocks", []):
                                if b.get("type") == "thought":
                                    b["bullets"] = ai_thinking.get("bullets", b.get("bullets", []))
                                    if ai_thinking.get("duration"):
                                        b["duration"] = ai_thinking["duration"]
                        existing_steps = c_sess.get("plan_steps", [])
                        has_progressed = any(s.get("status") in ["COMPLETED", "FAIL"] for s in existing_steps)
                        if not has_progressed and ai_steps:
                            c_sess["plan_steps"] = ai_steps
                            for b in c_sess.get("timeline_blocks", []):
                                if b.get("type") == "todo_list":
                                    b["total_count"] = len(ai_steps)
                                    b["title"] = f"更新任务清单 · 0/{len(ai_steps)} 已完成"
                                    b["items"] = [
                                        {"title": s["title"], "desc": s.get("desc", ""), "status": s.get("status", "READY"), "diff_type": "added"}
                                        for s in ai_steps
                                    ]
                        self._save_session(session_id)
                except Exception as e:
                    logger.warning(f"异步富化任务会话 [{session_id}] AI 推演异常: {e}")

            except Exception as ex:
                logger.error(f"后台规划与派发任务异常: {ex}", exc_info=True)

        self.executor.submit(_async_plan_and_dispatch)

        return session_id

    def approve_session(self, session_id: str) -> bool:
        """人工审批放行：唤醒任务并开始向各设备分发执行"""
        session = self.sessions.get(session_id)
        if not session or session["status"] != "AWAITING_APPROVAL":
            return False

        session["status"] = "RUNNING"
        for s in session["plan_steps"]:
            s["status"] = "APPROVED"

        if session.get("is_systemic_suite"):
            cases = session.get("suite_data", {}).get("cases", [])
            if cases:
                self.executor.submit(self._systemic_suite_runner, session_id, cases, session.get("keep_state", True))
                return True

        for dev_id in session["target_devices"]:
            if dev_id in session["devices"]:
                session["devices"][dev_id]["status"] = "QUEUED"
                session["devices"][dev_id]["action"] = "人工审批通过，已进入执行队列"
                session["devices"][dev_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 人工审批放行通过，开始调度执行")
            self.executor.submit(self._device_worker, session_id, dev_id, session["goal"], session["case_name"], session["test_mode"])
        return True

    def _record_bridged_turn(self, session: Dict[str, Any], clean_msg: str, notice_msg: str, attachments: Optional[List[Dict[str, Any]]] = None):
        """记录人机协同智能桥接在时间线和会话上下文中的事实轨迹"""
        try:
            turns = MemoryManager.ensure_session_turns(session)
            turn_id = len(turns) + 1
            if "timeline_blocks" not in session or not isinstance(session["timeline_blocks"], list):
                session["timeline_blocks"] = []
            session["timeline_blocks"].append(
                TimelineManager.create_user_block(clean_msg, turn_id=turn_id, attachments=attachments)
            )
            session["timeline_blocks"].append(
                TimelineManager.create_system_notice_block(notice_msg, turn_id=turn_id)
            )
            now_str = datetime.now().strftime("%H:%M:%S")
            if "messages" not in session or not isinstance(session["messages"], list):
                session["messages"] = []
            session["messages"].append({
                "role": "user",
                "content": clean_msg,
                "attachments": attachments or [],
                "timestamp": now_str
            })
            self._save_session(session.get("session_id", ""))
        except Exception as e:
            logger.warning(f"记录协同桥接轨迹异常: {e}")

    def append_session_message(self, session_id: str, message: str, provider: Optional[str] = None, model: Optional[str] = None, attachments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        在已有会话中追加新一轮测试意图 (Turn)，保持会话记忆与事实状态机，原地接续执行
        集成 Intent Gate 意图拦截、HITL 协同桥接与情境差量动态规划
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        clean_msg = message.strip()

        # -------------------------------------------------------------
        # 1. 意图拦截中枢 (Intent Gate)：精准识别控制指令 (停止/终止/取消/退出/结束/stop/cancel/quit)
        # -------------------------------------------------------------
        STOP_COMMAND_PATTERN = re.compile(
            r"^\s*(?:立即|马上|强制|请)?\s*(停止|终止|取消|退出|结束|停|停下|停下来|别测了|别跑了|stop|cancel|quit|abort|exit)\s*(?:当前)?\s*(任务|测试|执行|会话|流程)?[!！。.]*\s*$",
            re.IGNORECASE
        )
        if STOP_COMMAND_PATTERN.match(clean_msg):
            logger.info(f"🛑 [Intent Gate] 拦截到用户主动控制指令【{clean_msg}】，立即安全熔断会话 [{session_id}]")
            self.stop_session(session_id)
            session["hitl_decision"] = None
            try:
                decision_file = BASE_DIR / "scratch" / f"decision_{session_id}.json"
                decision_file.parent.mkdir(parents=True, exist_ok=True)
                decision_file.write_text(json.dumps({
                    "status": "CANCELLED",
                    "decision_type": "cancel",
                    "reason": "用户主动终止了测试任务"
                }, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.warning(f"写入协同取消文件异常: {e}")

            if "timeline_blocks" not in session or not isinstance(session["timeline_blocks"], list):
                session["timeline_blocks"] = []
            turns = MemoryManager.ensure_session_turns(session)
            new_turn_id = len(turns) + 1
            session["timeline_blocks"].append(
                TimelineManager.create_user_block(clean_msg, turn_id=new_turn_id, attachments=attachments)
            )
            session["timeline_blocks"].append(
                TimelineManager.create_system_notice_block("用户已主动终止测试任务", turn_id=new_turn_id)
            )
            self._save_session(session_id)
            return {
                "success": True,
                "stopped": True,
                "session_id": session_id,
                "message": "用户已主动终止测试任务"
            }

        # -------------------------------------------------------------
        # 2. 协同联动 (HITL Collaborative Bridge)：若任务处于挂起等待状态，将输入智能衔接为决策数据
        # -------------------------------------------------------------
        hitl = session.get("hitl_decision")
        is_waiting_hitl = (session.get("status") == "WAITING_USER_INPUT" or bool(hitl))
        if is_waiting_hitl and hitl:
            mode = hitl.get("mode", "credential")
            logger.info(f"🤝 [HITL Bridge] 检测到人机协同挂起 (mode={mode})，尝试将输入【{clean_msg}】智能衔接为决策数据")

            # 2.1 用户表达手动完成
            if re.search(r"^(?:我)?(?:已|已经)?(?:完成|完成了|弄好|搞定|做完|处理完|好了|搞定了)[!！。.]*$", clean_msg) or clean_msg.lower() in ["done", "manual_done", "finished"]:
                self.resolve_decision(session_id, {"decision_type": "manual_done"})
                notice_msg = "人机协同：已确认手动完成并恢复自动化推进"
                self._record_bridged_turn(session, clean_msg, notice_msg, attachments)
                return {"success": True, "resolved_hitl": True, "decision_type": "manual_done", "message": "已确认完成并恢复自动化"}

            # 2.2 用户表达跳过
            if re.search(r"^(?:直接)?(?:跳过|略过)[!！。.]*$", clean_msg) or clean_msg.lower() in ["skip", "pass"]:
                self.resolve_decision(session_id, {"decision_type": "skip"})
                notice_msg = "人机协同：已跳过当前步骤并恢复自动化推进"
                self._record_bridged_turn(session, clean_msg, notice_msg, attachments)
                return {"success": True, "resolved_hitl": True, "decision_type": "skip", "message": "已跳过该步骤并恢复自动化"}

            # 2.3 短信验证码模式：匹配 4~8 位数字（兼容中文上下文，不用 \\b 免受 Unicode 词分界影响）
            if mode == "sms_code":
                sms_match = re.search(r"(?<!\d)(\d{4,8})(?!\d)", clean_msg)
                if sms_match:
                    code = sms_match.group(1)
                    self.resolve_decision(session_id, {
                        "decision_type": "inject_sms",
                        "sms_code": code
                    })
                    notice_msg = f"人机协同：已自动衔接注入短信验证码【{code}】"
                    self._record_bridged_turn(session, clean_msg, notice_msg, attachments)
                    return {"success": True, "resolved_hitl": True, "decision_type": "inject_sms", "message": f"已自动将短信验证码【{code}】衔接注入"}

            # 2.4 手机号待发送模式：匹配 11 位以 1 开头的手机号（兼容中文上下文）
            elif mode == "phone_input":
                phone_match = re.search(r"(?<!\d)(1\d{10})(?!\d)", clean_msg)
                if phone_match:
                    phone = phone_match.group(1)
                    self.resolve_decision(session_id, {
                        "decision_type": "inject_phone",
                        "account": phone
                    })
                    notice_msg = f"人机协同：已自动衔接注入手机号【{phone}】"
                    self._record_bridged_turn(session, clean_msg, notice_msg, attachments)
                    return {"success": True, "resolved_hitl": True, "decision_type": "inject_phone", "message": f"已自动将手机号【{phone}】衔接注入"}

            # 2.5 账号密码登录凭据模式
            elif mode == "credential":
                parts = clean_msg.split()
                if len(parts) >= 2:
                    acc, pwd = parts[0], parts[1]
                else:
                    acc, pwd = clean_msg, ""
                self.resolve_decision(session_id, {
                    "decision_type": "inject",
                    "account": acc,
                    "password": pwd
                })
                notice_msg = f"人机协同：已自动衔接注入登录凭据【{acc}】"
                self._record_bridged_turn(session, clean_msg, notice_msg, attachments)
                return {"success": True, "resolved_hitl": True, "decision_type": "inject", "message": "已自动将账号凭据衔接注入"}

            # 2.6 AI 自主生成的人机协同字段
            elif hitl.get("type") == "ai_generated" or (hitl.get("fields") and len(hitl.get("fields", [])) > 0):
                fields = hitl.get("fields", [])
                if len(fields) == 1:
                    f_key = fields[0].get("key", "input")
                    self.resolve_decision(session_id, {
                        "decision_type": "ai_submit",
                        "inputs": {f_key: clean_msg}
                    })
                    notice_msg = f"人机协同：已自动衔接注入输入参数【{clean_msg}】"
                    self._record_bridged_turn(session, clean_msg, notice_msg, attachments)
                    return {"success": True, "resolved_hitl": True, "decision_type": "ai_submit", "message": "已自动将输入参数衔接注入"}

        # -------------------------------------------------------------
        # 3. 正常测试意图追加 (Turn)：动态差量规划，移除死板伪模板
        # -------------------------------------------------------------
        if provider:
            session["provider"] = provider
        if model:
            session["model"] = model

        turns = MemoryManager.ensure_session_turns(session)
        now_str = datetime.now().strftime("%H:%M:%S")

        if "messages" not in session or not isinstance(session["messages"], list):
            session["messages"] = []
        session["messages"].append({
            "role": "user",
            "content": clean_msg,
            "attachments": attachments or [],
            "timestamp": now_str
        })
        if attachments:
            if "attachments" not in session:
                session["attachments"] = []
            session["attachments"].extend(attachments)

        new_turn_id = len(turns) + 1
        new_turn = MemoryManager.create_turn(new_turn_id, clean_msg)
        if attachments:
            new_turn["attachments"] = attachments

        # 动态情境规划：根据端侧状态与意图子句拆解，绝不使用死板的 2 步伪模板
        dev_ctx = {"is_foreground": True, "scene_type": "APP_RUNNING"}
        raw_steps = self._decompose_plan_steps(clean_msg, is_auto=True, device_context=dev_ctx)
        turn_steps = []
        for idx, s in enumerate(raw_steps):
            turn_steps.append({
                "step_id": idx + 1,
                "step_number": idx + 1,
                "title": s.get("title", f"步骤 {idx+1}"),
                "desc": s.get("desc", ""),
                "status": "RUNNING" if idx == 0 else "PENDING"
            })
        if not turn_steps:
            turn_steps = [{
                "step_id": 1,
                "step_number": 1,
                "title": f"执行追加意图：{clean_msg[:14]}",
                "desc": f"响应用户追加测试诉求【{clean_msg}】并执行端侧断言",
                "status": "RUNNING"
            }]

        new_turn["plan_steps"] = turn_steps
        turns.append(new_turn)

        previous_steps = list(session.get("plan_steps", []))
        session["plan_steps"] = turn_steps
        session["status"] = "RUNNING"
        session["is_success"] = None
        session["error_message"] = None

        # 向对话流注入新轮次用户提问、思考态与任务清单
        if "timeline_blocks" not in session or not isinstance(session["timeline_blocks"], list):
            session["timeline_blocks"] = []
        session["timeline_blocks"].append(
            TimelineManager.create_user_block(clean_msg, turn_id=new_turn_id, attachments=attachments)
        )
        step_titles_str = "、".join([s["title"] for s in turn_steps[:3]])
        session["timeline_blocks"].append(
            TimelineManager.create_thought_block(
                duration="0.8s",
                bullets=[
                    {"tag": "意图深度解析", "content": f"深入理解本轮追加测试诉求【{clean_msg[:24]}】"},
                    {"tag": "动态规划路径", "content": f"就地继承前序端侧状态，规划差量执行阶段：{step_titles_str}"}
                ],
                turn_id=new_turn_id,
                is_done=False
            )
        )
        session["timeline_blocks"].append(
            TimelineManager.create_todo_block(turn_steps, previous_steps=previous_steps, turn_id=new_turn_id)
        )

        # 为各设备记录日志
        for dev_id, dev in session.get("devices", {}).items():
            dev["logs"].append(f"[{now_str}] 💬 [多轮对话追加 Turn {new_turn_id}]: {message}")
            dev["action"] = f"响应第 {new_turn_id} 轮追加指令: {message[:16]}..."

        target_devs = session.get("target_devices", [])
        if not target_devs and "devices" in session:
            target_devs = list(session["devices"].keys())
        for dev_id in target_devs:
            if dev_id in session.get("devices", {}):
                session["devices"][dev_id]["status"] = "QUEUED"
            self.executor.submit(
                self._device_worker,
                session_id,
                dev_id,
                message,
                session.get("case_name", "auto_flow"),
                session.get("test_mode", "real"),
                new_turn_id
            )

        self._save_session(session_id)
        return {"success": True, "session_id": session_id, "turn_id": new_turn_id, "turns_count": len(turns)}
