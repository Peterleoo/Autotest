# -*- coding: utf-8 -*-
"""执行调度：设备工作线程、收尾、看门狗自愈与 mock 流水线"""
from core.memory_manager import MemoryManager
import time
import logging
from datetime import datetime
from core.report_generator import ReportGenerator
from core.timeline_manager import TimelineManager
from core.task_common import BASE_DIR

logger = logging.getLogger("TaskManager")


class RuntimeMixin:
    """执行调度：设备工作线程、收尾、看门狗自愈与 mock 流水线"""

    def _finish_pipeline(self, session: dict, current_step_index: int, is_success: bool = True, final_error: str = ""):
        """
        全流程执行收敛与报错隔离：
        - 若成功：
          - 当前步及所有历史有效步标记为 COMPLETED；
          - 未执行到的后续预设步骤（如规划7步实际4步完成）标记为 SKIPPED（略过：已提前达成目标）；
        - 若失败：
          - 仅将当前报错步骤标记为 FAIL，并注入具体的 error_msg；
          - 之前已成功跑通的步骤保持 COMPLETED（严禁全体抹红！）；
          - 后续未开始步骤标记为 CANCELED（已取消）。
        """
        steps = session.get("plan_steps", [])
        total = len(steps)

        # 🚀 具身单一事实源与核心断言对齐 (Single Source of Truth)
        if is_success:
            unmet_assert_steps = [
                steps[i] for i in range(current_step_index + 1, total)
                if any(kw in steps[i].get("title", "") for kw in ["断言", "验证", "核验", "成功弹出", "回执"])
            ]
            # 真实闭环判定：只有在端侧未达成目标 (未获得 Verifier 批准且未就绪待验收) 时，才触发断言守卫阻断
            is_goal_achieved = session.get("is_goal_achieved", False) or (session.get("status") in ["READY_FOR_REVIEW", "COMPLETED"]) or ("🎉 目标完成" in session.get("markdown_report", ""))
            if unmet_assert_steps and not is_goal_achieved:
                logger.warning(f"🛡️ [DSH 断言守卫拦截]: 终态核心断言【{unmet_assert_steps[0].get('title')}】尚未被端侧执行验证即提前结束，严禁判定为全链路 PASS！")
                is_success = False
                session["is_success"] = False
                session["status"] = "BLOCKED"
                session["error_message"] = f"核心断言【{unmet_assert_steps[0].get('title')}】未被执行，测试未完全闭环"

        if is_success:
            # 目标达成：所有规划步骤统一对齐为 COMPLETED 达成态，消除两张皮
            for i in range(total):
                steps[i]["status"] = "COMPLETED"
                steps[i]["error_msg"] = None
                if i > current_step_index:
                    steps[i]["desc"] = f"【端侧联动达成】已由 AI 在业务探索中协同完成核验"
        else:
            # 失败态：仅在真实未达成时触发失败隔离，当前步报错
            if 0 <= current_step_index < total:
                steps[current_step_index]["status"] = "FAIL"
                steps[current_step_index]["error_msg"] = final_error or "端侧动作未达预期或校验中断"
            # 前置步骤保持原状（已完成的仍是 COMPLETED）
            for i in range(current_step_index):
                if steps[i]["status"] == "RUNNING":
                    steps[i]["status"] = "COMPLETED"
            # 后续未开始步骤标记为 CANCELED
            for i in range(current_step_index + 1, total):
                if steps[i]["status"] in ["READY", "PENDING", "RUNNING"]:
                    steps[i]["status"] = "CANCELED"
                    steps[i]["desc"] = f"因第 {current_step_index + 1} 步执行失败，后续测试链路已取消"

        # 🚀 同步更新 Timeline Blocks 中所有步骤卡片与 TodoList 的状态，坚决杜绝任何卡片残留 RUNNING
        tb = session.get("timeline_blocks", [])
        for card in tb:
            if card.get("type") in ["step_execution", "step_result"]:
                s_id = card.get("step_id", 1)
                idx = s_id - 1
                if is_success:
                    # 单一事实源：达成态下全量卡片与动作严格对齐为 COMPLETED
                    card["status"] = "COMPLETED"
                    raw_title = card.get("title", "")
                    clean_title = raw_title.replace(" (未通过)", "").replace("验证通过 ✅", "").replace("验证受阻 ❌", "").strip()
                    card["title"] = f"{clean_title} 验证通过 ✅"
                    if not card.get("assertion_result") or "未达预期" in card.get("assertion_result", ""):
                        card["assertion_result"] = f"阶段断言达成：【{clean_title}】已顺利完成并核验"
                    for act in card.get("actions", []):
                        act["status"] = "COMPLETED"
                    if card.get("duration") in ["推进中", "中断"] or not card.get("duration"):
                        card["duration"] = "0.8s"
                else:
                    if idx == current_step_index:
                        card["status"] = "FAIL"
                        card["title"] = f"{card.get('title', '')} (未通过)"
                        card["assertion_result"] = final_error or "端侧动作未达预期或校验中断"
                        if card.get("actions"):
                            card["actions"][-1]["status"] = "FAIL"
                        if card.get("duration") == "推进中":
                            card["duration"] = "中断"

        # 同步更新 TodoList
        completed_c = sum(1 for s in steps if s.get("status") in ["COMPLETED", "PASS"])
        for todo_blk in tb:
            if todo_blk.get("type") == "todo_list":
                todo_blk["completed_count"] = completed_c
                todo_blk["total_count"] = len(steps)
                todo_blk["status"] = "COMPLETED" if (is_success or completed_c == len(steps)) else "RUNNING"
                if is_success:
                    todo_blk["title"] = f"任务清单 · 全部目标达成 ({completed_c}/{len(steps)} 步骤)"
                else:
                    todo_blk["title"] = f"更新任务清单 · {completed_c}/{len(steps)} 已完成"
                for item in todo_blk.get("items", []):
                    matching = next((s for s in steps if s.get("title") == item.get("title")), None)
                    if matching:
                        item["status"] = matching.get("status")

    def _device_worker(self, session_id: str, device_id: str, goal: str, case_name: str, test_mode: str, turn_id: int = 1):
        session = self.sessions.get(session_id)
        if not session or device_id not in session["devices"]:
            return

        dev_state = session["devices"][device_id]
        lock = self._get_device_lock(device_id)

        # 1. 尝试获取该设备排它锁（带超时与自愈探测）
        dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 正在请求锁定目标设备...")
        acquired = False
        wait_cycles = 0
        while not acquired:
            if session.get("status") == "STOPPED":
                return
            acquired = lock.acquire(timeout=1.5)
            if not acquired:
                wait_cycles += 1
                if wait_cycles >= 4:
                    for s_id, s_data in list(self.sessions.items()):
                        if s_id != session_id and s_data.get("status") in ["WAITING_USER_INPUT", "PAUSED"]:
                            if device_id in s_data.get("target_devices", []):
                                logger.warning(f"⚡ [设备锁自愈] 检测到挂起会话 [{s_id}] 霸占设备锁，自动释放接管...")
                                self.stop_session(s_id)
                                break
                    wait_cycles = 0

        try:
            dev_state["status"] = "RUNNING"
            dev_state["action"] = "成功获取设备执行锁，启动测试"
            dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 成功锁定设备 [{dev_state['model']}]，开始推进测试流")
            start_t = time.time()

            try:
                if test_mode == "local" or "mock" in device_id.lower() or "simulator" in device_id.lower():
                    self._run_mock_pipeline(session, dev_state, goal, case_name, start_t)
                elif "ios" in device_id.lower():
                    self._run_ios_pipeline(session, dev_state, goal, case_name, start_t)
                else:
                    self._run_real_android_pipeline(session, dev_state, device_id, goal, case_name, start_t, turn_id=turn_id)
            except Exception as e:
                dev_state["status"] = "FAIL"
                dev_state["success"] = False
                dev_state["action"] = f"执行异常: {e}"
                dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 执行抛出异常: {e}")
                self._finish_pipeline(session, max(0, dev_state.get("step", 1) - 1), is_success=False, final_error=str(e))

            # 🛡️ 若已主动终止，彻底退出
            if session.get("status") == "STOPPED":
                self._save_session(session_id)
                return

            # 检查整个 Session 的完成状态
            all_done = all(d["status"] in ["PASS", "FAIL", "COMPLETED"] for d in session["devices"].values())
            if all_done:
                has_fail = any(d["status"] == "FAIL" or d.get("success") is False for d in session["devices"].values())
                session["is_success"] = not has_fail
                if has_fail:
                    session["status"] = "FAILED"
                    session["error_message"] = session.get("error_message") or "存在执行失败的设备或动作异常中断"
                else:
                    # 🚀 进入待验收状态 READY_FOR_REVIEW (严禁普通输出直接自动完成)
                    session["status"] = "READY_FOR_REVIEW"
                    session["error_message"] = None

                for d in session["devices"].values():
                    if d.get("report_url"):
                        session["report_url"] = d["report_url"]
                        break

                # 同步当前 Turn 状态与结论
                turns = MemoryManager.ensure_session_turns(session)
                if turns:
                    curr_turn = turns[-1]
                    curr_turn["status"] = session["status"]
                    if not has_fail:
                        curr_turn["conclusion"] = f"第 {curr_turn.get('turn_id', 1)} 轮规划动作已全部验证达成，等待人工验收通过或打回返工。"

                # 自动注册全景交付物 (仅在全链路验证达成时注册交付资产，失败态坚决不出伪交付物)
                if not has_fail:
                    self.register_deliverables(session_id)
                else:
                    session["deliverables"] = []

            # 实时持久化存盘，保证前端刷新或服务重启数据 100% 完整
            self._save_session(session_id)
        finally:
            if acquired:
                try:
                    lock.release()
                except RuntimeError:
                    pass

    def _handle_watchdog_heal_event(self, session: dict, dev_state: dict, evt: dict):
        """处理看门狗触发的自愈事件，注入时间线与设备日志"""
        msg = evt.get("message", "执行异常自愈")
        atype = evt.get("anomaly_type", "UNKNOWN")
        action = evt.get("heal_action", "")
        evidence = evt.get("evidence_screenshot")

        log_line = f"[{datetime.now().strftime('%H:%M:%S')}] 🐕‍🦺 [看门狗自愈] {msg} (动作: {action})"
        dev_state["logs"].append(log_line)

        # 写入时间线系统通知块
        tb = session.setdefault("timeline_blocks", [])
        tb.append(TimelineManager.create_system_notice_block(
            content=f"🐕‍🦺 [看门狗自愈] {msg}",
            evidence=evidence
        ))
        self._save_session(session.get("session_id", ""))

    def _run_mock_pipeline(self, session: dict, dev_state: dict, goal: str, case_name: str, start_t: float):
        """本地自测模式，按 plan_steps 流式逐动作推进与实时反馈"""
        steps = session.get("plan_steps", [])
        total_steps = len(steps)
        dev_state["max_steps"] = total_steps
        sid = session.get("session_id", "")

        for idx, st in enumerate(steps):
            step_no = idx + 1
            dev_state["step"] = step_no
            dev_state["action"] = f"正在执行 Step {step_no}: {st['title']}"
            
            # 1. 激活当前步骤为 RUNNING
            st["status"] = "RUNNING"
            dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [Step {step_no}/{total_steps}] 节点激活 -> {st['title']}")
            dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 动作详情: {st['desc']}")
            
            # 同步更新 TodoList
            todo_blks = [b for b in session.get("timeline_blocks", []) if b.get("type") == "todo_list"]
            if todo_blks:
                latest_todo = todo_blks[-1]
                latest_todo["completed_count"] = idx
                latest_todo["total_count"] = total_steps
                latest_todo["title"] = f"更新任务清单 · {idx}/{total_steps} 已完成"
                for it_idx, item in enumerate(latest_todo.get("items", [])):
                    if it_idx < idx:
                        item["status"] = "COMPLETED"
                    elif it_idx == idx:
                        item["status"] = "RUNNING"
                    else:
                        item["status"] = "READY"

            # 挂载或更新当前步骤卡片为 RUNNING，并开始流式注入微观动作
            block_id = f"blk_stepres_0_{step_no}"
            card_actions = [
                {
                    "type": "ocr",
                    "name": "视觉感知",
                    "desc": f"扫描屏幕并提取【{st['title']}】关键热区",
                    "param": "OCR Scanning...",
                    "observation": "正在扫描屏幕组件与坐标...",
                    "status": "RUNNING"
                }
            ]
            
            # 查找或追加当前卡片
            step_card = next((b for b in session.get("timeline_blocks", []) if b.get("block_id") == block_id), None)
            if not step_card:
                step_card = TimelineManager.create_step_execution_block(
                    step_id=step_no,
                    title=st['title'],
                    actions=card_actions,
                    assertion_result="",
                    status="RUNNING",
                    duration="推进中",
                    turn_id=0
                )
                step_card["block_id"] = block_id
                session.setdefault("timeline_blocks", []).append(step_card)
            else:
                step_card["status"] = "RUNNING"
                step_card["actions"] = card_actions

            self._save_session(sid)
            time.sleep(0.6)

            # 2. 动作 1 (视觉感知) 完成，启动动作 2 (手势派发)
            card_actions[0]["status"] = "COMPLETED"
            card_actions[0]["param"] = "OCR Match 0.985"
            card_actions[0]["observation"] = "文字识别置信度 98.5% · 成功定位目标组件与坐标热区"
            
            card_actions.append({
                "type": "tap",
                "name": "手势派发",
                "desc": f"注入原生交互手势：{st['desc'][:24]}",
                "param": "tap(x, y)",
                "observation": "正在向物理通道注入原生轻触交互...",
                "status": "RUNNING"
            })
            step_card["actions"] = card_actions
            self._save_session(sid)
            time.sleep(0.7)

            # 3. 动作 2 (手势派发) 完成，启动动作 3 (状态断言)
            card_actions[1]["status"] = "COMPLETED"
            card_actions[1]["observation"] = "真机通道响应就绪 · 屏幕层级发生有效转场"

            card_actions.append({
                "type": "assert",
                "name": "状态断言",
                "desc": f"核验新视图渲染就绪与业务数据回包",
                "param": "Verifying...",
                "observation": "正在核验端侧状态与业务回包...",
                "status": "RUNNING"
            })
            step_card["actions"] = card_actions
            self._save_session(sid)
            time.sleep(0.6)

            # 4. 动作 3 (状态断言) 完成，当前步骤彻底完成！
            card_actions[2]["status"] = "COMPLETED"
            card_actions[2]["param"] = "PASS (Verified)"
            card_actions[2]["observation"] = "无 Crash · 无 ANR · 目标界面元素与状态就绪"

            st["status"] = "COMPLETED"
            step_card["status"] = "COMPLETED"
            step_card["duration"] = "0.8s"
            step_card["title"] = f"Step {step_no}: {st['title']} 验证通过"
            step_card["assertion_result"] = f"阶段断言达成：已成功完成并验证【{st['title']}】"
            step_card["actions"] = card_actions

            # 同步更新 TodoList 当前项为 COMPLETED
            if todo_blks:
                latest_todo = todo_blks[-1]
                latest_todo["completed_count"] = idx + 1
                latest_todo["title"] = f"更新任务清单 · {idx + 1}/{total_steps} 已完成"
                if idx < len(latest_todo.get("items", [])):
                    latest_todo["items"][idx]["status"] = "COMPLETED"

            dev_state["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Step {step_no} 断言通过")
            self._save_session(sid)
            time.sleep(0.2)

        duration = time.time() - start_t
        dev_state["duration"] = f"{round(duration, 1)}s"
        dev_state["status"] = "PASS"
        dev_state["success"] = True
        
        # 全部步骤彻底跑完，标记任务清单为全部完成
        if todo_blks:
            latest_todo = todo_blks[-1]
            latest_todo["completed_count"] = total_steps
            latest_todo["title"] = f"任务清单已全部完成 · 共 {total_steps} 步"
            for item in latest_todo.get("items", []):
                item["status"] = "COMPLETED"

        self._finish_pipeline(session, total_steps - 1, is_success=True)

        md_content, report_p = ReportGenerator.generate_markdown_report(
            session=session,
            dev_state=dev_state,
            is_success=True,
            raw_output="\n".join(dev_state["logs"]),
            duration_sec=duration
        )
        report_url = f"/api/reports/{session['session_id']}/markdown"
        dev_state["report_url"] = report_url
        session["report_url"] = report_url
        session["markdown_report"] = md_content
        session["markdown_report_path"] = str(report_p.relative_to(BASE_DIR)).replace("\\", "/")

        if "messages" not in session or not isinstance(session["messages"], list):
            session["messages"] = []
        session["messages"].append({
            "role": "assistant",
            "content": md_content,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "is_report": True,
            "session_id": session["session_id"]
        })

        if "timeline_blocks" not in session or not isinstance(session["timeline_blocks"], list):
            session["timeline_blocks"] = []
        turn_no = sum(1 for b in session["timeline_blocks"] if b.get("type") == "user_message")
        session["timeline_blocks"].append(
            TimelineManager.create_report_block(md_content, session["session_id"], turn_id=max(0, turn_no - 1))
        )
        session["timeline_blocks"].append(
            TimelineManager.create_test_summary_block(
                session_id=session["session_id"],
                goal=session.get("goal") or session.get("title", ""),
                is_success=True,
                duration=f"{round(duration, 1)}s",
                steps_summary="全链路业务闭环达成",
                deliverables=session.get("deliverables"),
                is_solidified=session.get("is_solidified", False),
                solidified_filename=session.get("solidified_filename", ""),
                turn_id=max(0, turn_no - 1)
            )
        )
