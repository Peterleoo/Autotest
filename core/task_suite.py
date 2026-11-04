# -*- coding: utf-8 -*-
"""系统级测试套件：保存/读取、串联执行与文档驱动套件分发"""
from core.memory_manager import MemoryManager
import time
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from core.report_generator import ReportGenerator
from core.timeline_manager import TimelineManager
from core.task_common import BASE_DIR, TEST_SUITES_STORE_DIR

logger = logging.getLogger("TaskManager")


class SuiteMixin:
    """系统级测试套件：保存/读取、串联执行与文档驱动套件分发"""

    def save_test_suite(self, suite_data: dict) -> Dict[str, Any]:
        """将用例套件持久化存储到本地 data/test_suites/ 目录供后续随时复跑"""
        if not isinstance(suite_data, dict):
            raise ValueError("suite_data 必须为字典对象")

        suite_id = suite_data.get("suite_id") or suite_data.get("id")
        if not suite_id:
            suite_id = f"suite_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cases = suite_data.get("cases") or []
        record = {
            "suite_id": suite_id,
            "suite_title": suite_data.get("suite_title") or "系统级测试套件",
            "doc_filename": suite_data.get("doc_filename") or "",
            "keep_state": bool(suite_data.get("keep_state", True)),
            "cases": cases,
            "case_count": len(cases),
            "created_at": suite_data.get("created_at") or now_str,
            "updated_at": now_str,
            "tags": suite_data.get("tags") or ["系统回归", "需求驱动"]
        }
        target_path = TEST_SUITES_STORE_DIR / f"{suite_id}.json"
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ 系统测试套件已成功存盘: {target_path} (共 {record['case_count']} 条用例)")
        return record

    def list_test_suites(self) -> List[Dict[str, Any]]:
        """获取所有已持久化保存的测试套件列表"""
        suites = []
        for p in TEST_SUITES_STORE_DIR.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not data.get("suite_id"):
                        data["suite_id"] = p.stem
                    data["file_mtime"] = p.stat().st_mtime
                    suites.append(data)
            except Exception as e:
                logger.warning(f"读取套件文件 {p.name} 失败: {e}")
        suites.sort(key=lambda s: s.get("file_mtime", 0), reverse=True)
        return suites

    def get_test_suite(self, suite_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取已保存的测试套件"""
        p = TEST_SUITES_STORE_DIR / f"{suite_id}.json"
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"读取套件 {suite_id} 异常: {e}")
            return None

    def run_systemic_suite(
        self,
        session_id: Optional[str] = None,
        suite_data: Optional[Dict[str, Any]] = None,
        keep_state: bool = True
    ) -> Dict[str, Any]:
        """
        以系统级串联模式执行测试用例套件：
        1. 将勾选的用例序列注入会话作为多轮任务或流水线各阶段；
        2. 当 keep_state=True 时在用例切换间不 kill 进程，原地探索接续，上一条登录态直接继承；
        3. 执行完成后生成系统级全景报告。
        """
        if not suite_data or not isinstance(suite_data, dict):
            raise ValueError("suite_data 必须为包含 cases 的字典对象")

        cases = [c for c in suite_data.get("cases", []) if c.get("checked", True) or "checked" not in c]
        if not cases:
            cases = suite_data.get("cases", [])
        if not cases:
            raise ValueError("测试套件中无有效可用用例")

        suite_title = suite_data.get("suite_title") or "系统级端到端测试套件"

        # 统一生成用例套件的标准执行步骤与推演元数据
        plan_steps = []
        for idx, c in enumerate(cases):
            prio = c.get("priority", "P1")
            mod = c.get("module", "业务流程")
            title = c.get("title", f"用例 {idx+1}")
            plan_steps.append({
                "step_id": idx + 1,
                "step_number": idx + 1,
                "title": f"[{prio}] {mod}: {title}",
                "desc": f"目标: {c.get('goal', '')} | 断言: {c.get('assert_rule', '')}",
                "status": "RUNNING" if idx == 0 else "READY",
                "case_id": c.get("id", f"tc-{idx+1:02d}"),
                "depends_on": c.get("depends_on", "")
            })

        bullets = [
            {"tag": "系统测试套件装配", "content": f"已载入【{suite_title}】，共选定 {len(cases)} 项端到端业务用例"},
            {"tag": "状态现场继承策略", "content": "【现场串联】已开启：用例间保持应用现场不冷启，直接接续执行" if keep_state else "【独立冷启动】：每项用例执行前重启应用保持纯净环境"},
            {"tag": "执行链路规划", "content": " ➔ ".join([c.get("title", f"用例{i+1}")[:10] for i, c in enumerate(cases[:3])])}
        ]

        init_thinking = {
            "duration": "推演中...",
            "bullets": bullets
        }

        user_goal = f"执行系统级测试套件【{suite_title}】（共 {len(cases)} 项用例，现场串联: {'开启' if keep_state else '关闭'}）"

        # 若未指定 session_id，或会话不存在，新建一个系统级测试会话
        session = self.sessions.get(session_id) if session_id else None
        if not session:
            device_ids = suite_data.get("device_ids")
            if not device_ids:
                from core.app_manager import AppManager
                app_mgr = AppManager()
                conn_devs = app_mgr.get_connected_devices()
                if not conn_devs:
                    raise ValueError("未检测到已连接的真机设备，请连接设备后重试")
                device_ids = [conn_devs[0] if isinstance(conn_devs[0], str) else conn_devs[0].get("id", "auto_device")]

            session_id = f"sess_suite_{datetime.now().strftime('%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

            init_timeline = [
                TimelineManager.create_user_block(user_goal, turn_id=0),
                TimelineManager.create_thought_block("0.5s", bullets, turn_id=0),
                TimelineManager.create_todo_block(plan_steps, turn_id=0)
            ]

            session = {
                "session_id": session_id,
                "title": suite_title[:24],
                "goal": user_goal,
                "case_name": "systemic_suite",
                "test_mode": "mock" if "mock" in device_ids[0].lower() else "real",
                "approval_mode": "auto",
                "provider": suite_data.get("provider"),
                "model": suite_data.get("model"),
                "app_id": suite_data.get("app_id") or "demo_app",
                "app_filename": suite_data.get("app_filename"),
                "app_package": suite_data.get("app_package"),
                "app_label": suite_data.get("app_label"),
                "app_activity": suite_data.get("app_activity"),
                "created_at": datetime.now().strftime("%H:%M:%S"),
                "timestamp": time.time(),
                "status": "RUNNING",
                "target_devices": device_ids,
                "thinking": init_thinking,
                "clarification": None,
                "attachments": [],
                "messages": [
                    {"role": "user", "content": user_goal, "timestamp": datetime.now().strftime("%H:%M:%S")}
                ],
                "turns": [{
                    "turn_id": 1,
                    "user_message": user_goal,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "thinking": init_thinking,
                    "plan_steps": plan_steps,
                    "actions": [],
                    "conclusion": "",
                    "status": "RUNNING"
                }],
                "fact_memory": MemoryManager.create_empty_fact_memory(),
                "deliverables": [],
                "rework_history": [],
                "token_stats": {
                    "total_tokens": 0,
                    "context_window": 1048576,
                    "pressure_level": "normal"
                },
                "timeline_blocks": init_timeline,
                "plan_steps": plan_steps,
                "devices": {},
                "report_url": "",
                "is_solidified": False,
                "solidified_filename": "",
                "solidified_module": "",
                "is_systemic_suite": True,
                "suite_data": suite_data,
                "keep_state": keep_state
            }

            for dev_id in device_ids:
                model_label = self._resolve_device_label(dev_id, session["test_mode"])
                platform = "iOS" if "ios" in dev_id.lower() or "iphone" in dev_id.lower() else "Android"
                session["devices"][dev_id] = {
                    "device_id": dev_id,
                    "model": model_label,
                    "platform": platform,
                    "status": "RUNNING",
                    "step": 0,
                    "max_steps": len(cases) * 5,
                    "action": f"启动系统套件执行: {cases[0].get('title')}",
                    "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 系统级测试套件已挂载，目标设备 [{model_label}]，开始串联执行..."],
                    "report_url": "",
                    "success": None,
                    "duration": "0s",
                    "start_time": time.time()
                }

            self.sessions[session_id] = session
            self.active_session_id = session_id
            self._save_session(session_id)
        else:
            session_id = session["session_id"]
            session["is_systemic_suite"] = True
            session["suite_data"] = suite_data
            session["keep_state"] = keep_state
            session["status"] = "RUNNING"
            session["goal"] = user_goal
            session["plan_steps"] = plan_steps
            turn_no = len(session.get("turns", [])) + 1
            session.setdefault("messages", []).append({
                "role": "user",
                "content": user_goal,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            session.setdefault("timeline_blocks", []).extend([
                TimelineManager.create_user_block(user_goal, turn_id=turn_no),
                TimelineManager.create_thought_block("0.5s", bullets, turn_id=turn_no),
                TimelineManager.create_todo_block(plan_steps, turn_id=turn_no)
            ])
            session.setdefault("turns", []).append({
                "turn_id": turn_no,
                "user_message": user_goal,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "thinking": init_thinking,
                "plan_steps": plan_steps,
                "actions": [],
                "conclusion": "",
                "status": "RUNNING"
            })
            for dev_id, d in session.get("devices", {}).items():
                d["status"] = "RUNNING"
                d["step"] = 0
                d["max_steps"] = len(cases) * 5
                d["action"] = f"启动系统套件执行: {cases[0].get('title')}"
                d["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 载入系统级测试套件，开始串联执行...")
                d["report_url"] = ""
                d["success"] = None
                d["duration"] = "0s"
                d["start_time"] = time.time()
            self._save_session(session_id)

        # 启动后台串联执行线程
        self.executor.submit(self._systemic_suite_runner, session_id, cases, keep_state)
        return {
            "success": True,
            "session_id": session_id,
            "cases_count": len(cases),
            "keep_state": keep_state,
            "message": f"系统级测试套件已启动，共 {len(cases)} 项用例"
        }

    def force_resume_doc_suite(self, session_id: str) -> bool:
        """用户在确认知情后，强制放行并恢复需求文档套件提炼与系统级测试"""
        cur_sess = self.sessions.get(session_id)
        if not cur_sess:
            return False
        cur_sess["force_run_doc_suite"] = True
        cur_sess["status"] = "PLANNING"
        cur_sess["timeline_blocks"] = [b for b in cur_sess.get("timeline_blocks", []) if b.get("type") != "doc_mismatch_guard"]
        self._save_session(session_id)

        doc_att = [a for a in cur_sess.get("attachments", []) if isinstance(a, dict) and a.get("is_doc")]
        if not doc_att:
            return False
        doc_entry = doc_att[0]
        doc_text = doc_entry.get("extracted_text") or ""
        if not doc_text and doc_entry.get("path"):
            from pathlib import Path as FilePath
            fp = FilePath(doc_entry["path"])
            if fp.exists():
                doc_text = fp.read_text(encoding="utf-8", errors="ignore")
        doc_filename = doc_entry.get("name") or doc_entry.get("filename") or "需求规格说明书.md"
        is_auto = cur_sess.get("approval_mode", "auto") == "auto"

        self.executor.submit(
            self._dispatch_doc_suite,
            session_id,
            doc_text,
            doc_filename,
            cur_sess.get("provider"),
            cur_sess.get("model"),
            is_auto,
            time.time()
        )
        return True

    def _dispatch_doc_suite(
        self,
        session_id: str,
        doc_text: str,
        doc_filename: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        is_auto: bool = True,
        t_decomp_start: Optional[float] = None
    ) -> bool:
        """从需求文档智能提炼业务用例套件并挂载时间线驱动执行"""
        from core.test_spec_synthesizer import TestSpecSynthesizer
        from core.timeline_manager import TimelineManager
        if t_decomp_start is None:
            t_decomp_start = time.time()

        cur_sess = self.sessions.get(session_id)
        if not cur_sess or cur_sess.get("status") in ["STOPPED", "FAILED"]:
            return False

        device_ids = cur_sess.get("target_devices", [])

        logger.info(f"📄 [Doc-Driven Engine] 正在从需求文档《{doc_filename}》智能提炼系统用例套件...")
        suite_res = TestSpecSynthesizer.synthesize_from_doc(doc_text, filename=doc_filename, provider=provider, model=model)
        cases = suite_res.get("cases", [])
        if not cases:
            return False

        suite_title = suite_res.get("suite_title") or "需求驱动系统测试用例套件"
        decomp_dur = round(time.time() - t_decomp_start + 0.35, 2)
        duration_str = f"{decomp_dur}s"

        cur_sess["is_systemic_suite"] = True
        cur_sess["suite_data"] = suite_res
        cur_sess["title"] = suite_title[:24]

        suite_plan_steps = []
        for idx, c_item in enumerate(cases):
            prio = c_item.get("priority", "P1")
            mod = c_item.get("module", "业务流程")
            c_title = c_item.get("title", f"用例 {idx+1}")
            suite_plan_steps.append({
                "step_id": idx + 1,
                "step_number": idx + 1,
                "title": f"[{prio}] {mod}: {c_title}",
                "desc": f"目标: {c_item.get('goal', '')} | 断言: {c_item.get('assert_rule', '')}",
                "status": "RUNNING" if idx == 0 else "READY",
                "case_id": c_item.get("id", f"tc-{idx+1:02d}"),
                "depends_on": c_item.get("depends_on", "")
            })

        final_thinking = {
            "duration": duration_str,
            "bullets": [
                {"tag": "需求文档语义萃取", "content": f"深度解析《{doc_filename}》，提炼生成【{suite_title}】共 {len(cases)} 项业务用例。"},
                {"tag": "系统测试套件编排", "content": f"装配完成：{' ➔ '.join([c_item.get('title','') for c_item in cases[:3]])}... 串联执行并继承现场状态。"},
                {"tag": "端侧断言与执行预案", "content": "逐项驱动目标真机执行各模块核心动作并核验业务断言，遇异常提供全景诊断。"}
            ]
        }

        cur_sess["thinking"] = final_thinking
        cur_sess["plan_steps"] = suite_plan_steps
        cur_sess["status"] = "RUNNING" if is_auto else "AWAITING_APPROVAL"
        if cur_sess.get("turns"):
            cur_sess["turns"][0]["thinking"] = final_thinking
            cur_sess["turns"][0]["plan_steps"] = suite_plan_steps
            cur_sess["turns"][0]["status"] = cur_sess["status"]

        tb = cur_sess.setdefault("timeline_blocks", [])
        cur_sess["timeline_blocks"] = [b for b in tb if b.get("type") != "doc_mismatch_guard"]
        tb = cur_sess["timeline_blocks"]

        thought_block = next((b for b in tb if b.get("type") == "thought"), None)
        if thought_block:
            thought_block["duration"] = duration_str
            thought_block["bullets"] = final_thinking["bullets"]

        # 注入 Generative UI Suite Builder 编排卡片 (契约式组件)
        tb.append(TimelineManager.create_suite_builder_block(
            suite_data=suite_res,
            session_id=session_id
        ))

        # 挂载或更新 todo 块
        tb.append(TimelineManager.create_todo_block(suite_plan_steps, turn_id=0))

        for dev_id in device_ids:
            if dev_id in cur_sess.get("devices", {}):
                cur_sess["devices"][dev_id]["action"] = f"正在启动系统测试套件: {cases[0].get('title', '')}" if is_auto else "等待人工审批套件执行..."
                cur_sess["devices"][dev_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 需求文档提炼就绪，装配 {len(cases)} 项用例：{' ➔ '.join([c_item.get('title','') for c_item in cases[:3]])}")

        self._save_session(session_id)

        if is_auto:
            self.executor.submit(self._systemic_suite_runner, session_id, cases, keep_state=True)
        return True

    def _systemic_suite_runner(self, session_id: str, cases: List[Dict[str, Any]], keep_state: bool):
        """后台串联执行系统级用例套件工作线程"""
        session = self.sessions.get(session_id)
        if not session:
            return

        target_devs = session.get("target_devices", []) or list(session.get("devices", {}).keys())
        if not target_devs:
            logger.error(f"🛑 [Suite Runner] 会话 [{session_id}] 无可用目标设备，终止套件执行")
            session["status"] = "FAILED"
            session["error_message"] = "未检测到可用的真机设备，系统测试套件无法执行"
            self._save_session(session_id)
            return
        primary_dev = target_devs[0]
        dev_state = session["devices"].get(primary_dev)
        if not dev_state:
            return

        start_t = time.time()
        logger.info(f"🚀 [Suite Runner] 开始串联执行系统测试套件 [{session_id}] (共 {len(cases)} 项用例, keep_state={keep_state})")

        overall_success = True
        failed_count = 0
        executed_cases_logs = []

        for idx, case in enumerate(cases):
            if session.get("status") in ["STOPPED", "CANCELLED"]:
                logger.info(f"🛑 [Suite Runner] 会话已主动终止，中断套件执行")
                break

            step_id = idx + 1
            case_title = case.get("title", f"用例 {step_id}")
            case_goal = case.get("goal", case_title)
            assert_rule = case.get("assert_rule", "验证页面状态正常")
            composite_goal = f"【系统测试用例 {step_id}/{len(cases)}: {case_title}】\n业务目标: {case_goal}\n断言验证: {assert_rule}"

            # 推进当前步骤状态
            self._advance_session_step(session, idx, default_title=f"执行用例 {step_id}: {case_title}", default_desc=case_goal)
            dev_state["step"] = (idx + 1) * 5 - 2
            dev_state["action"] = f"正在执行用例 {step_id}/{len(cases)}: {case_title}"
            dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ▶️ 开始执行用例 [{step_id}/{len(cases)}]: {case_title}")
            self._save_session(session_id)

            # 当 keep_state=True 时，第一项 turn_id=1 启动应用，后续项 turn_id > 1 原地接续，杜绝 kill 进程
            turn_id = (idx + 1) if keep_state else 1
            case_start_t = time.time()
            case_success = True

            try:
                if session.get("test_mode") == "local" or "mock" in primary_dev.lower() or "simulator" in primary_dev.lower():
                    time.sleep(1.0)
                    dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 模拟执行用例达成: {case_title}")
                    case_success = True
                else:
                    self._run_real_android_pipeline(
                        session=session,
                        dev_state=dev_state,
                        device_id=primary_dev,
                        goal=composite_goal,
                        case_name=f"case_{step_id}",
                        start_t=case_start_t,
                        turn_id=turn_id
                    )
                    case_success = (dev_state.get("status") != "FAIL" and dev_state.get("success") is not False)
            except Exception as e:
                logger.error(f"用例 {case_title} 执行异常: {e}")
                case_success = False
                dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 用例执行异常: {e}")

            executed_cases_logs.append({
                "id": case.get("id", f"tc-{step_id:02d}"),
                "title": case_title,
                "module": case.get("module", ""),
                "priority": case.get("priority", "P1"),
                "success": case_success,
                "cost": round(time.time() - case_start_t, 1)
            })

            # 更新当前步骤状态与设备进度
            dev_state["step"] = (idx + 1) * 5
            if case_success:
                self._update_session_step(session, idx, status="COMPLETED", detail=f"用例断言达成 (耗时 {round(time.time() - case_start_t, 1)}s)")
                dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 用例 [{step_id}/{len(cases)}] 验证通过: {case_title}")
            else:
                self._update_session_step(session, idx, status="FAIL", detail=f"用例执行未达成预期")
                dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 用例 [{step_id}/{len(cases)}] 执行失败: {case_title}")
                failed_count += 1
                overall_success = False

            self._save_session(session_id)

        # 全部用例串联执行完毕
        total_duration = time.time() - start_t
        dev_state["step"] = len(cases) * 5
        dev_state["duration"] = f"{round(total_duration, 1)}s"
        dev_state["status"] = "PASS" if overall_success else "FAIL"
        dev_state["success"] = overall_success
        session["is_success"] = overall_success
        session["status"] = "READY_FOR_REVIEW" if overall_success else "FAILED"

        # 生成系统级全景测试报告
        report_logs = "\n".join(dev_state.get("logs", []))
        md_content, report_p = ReportGenerator.generate_markdown_report(
            session=session,
            dev_state=dev_state,
            is_success=overall_success,
            raw_output=report_logs,
            duration_sec=total_duration
        )
        report_url = f"/api/reports/{session['session_id']}/markdown"
        dev_state["report_url"] = report_url
        session["report_url"] = report_url
        session["markdown_report"] = md_content
        session["markdown_report_path"] = str(report_p.relative_to(BASE_DIR)).replace("\\", "/")

        if overall_success:
            self.register_deliverables(session_id)

        self._save_session(session_id)
        logger.info(f"🏁 [Suite Runner] 系统测试套件 [{session_id}] 执行结束，整体通过: {overall_success} (失败: {failed_count}/{len(cases)})")
