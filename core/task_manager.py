from core.memory_manager import MemoryManager
import os
import re
import sys
import copy
import time
import json
import uuid
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from config.settings import settings
from config.ai_config import ai_config
from core.report_generator import ReportGenerator
from core.timeline_manager import TimelineManager
from core.device_watchdog import DeviceWatchdog, DEFAULT_WATCHDOG_TIMEOUT

logger = logging.getLogger("TaskManager")
from core.task_common import BASE_DIR, SESSIONS_STORE_DIR, TEST_SUITES_STORE_DIR  # noqa: F401
from core.task_timeline import TimelineViewMixin
from core.task_conversation import ConversationMixin
from core.task_planning import PlanningMixin
from core.task_runtime import RuntimeMixin
from core.task_device_pipeline import DevicePipelineMixin
from core.task_suite import SuiteMixin


class TaskManager(TimelineViewMixin, ConversationMixin, PlanningMixin, RuntimeMixin, DevicePipelineMixin, SuiteMixin):

    @staticmethod
    def format_duration_cn(seconds: float) -> str:
        """格式化耗时显示，如：'用时 5分53秒' 或 '用时 42秒'"""
        if seconds < 60:
            return f"用时 {max(1, int(round(seconds)))}秒"
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"用时 {mins}分{secs}秒"

    """
    多任务并发与多设备协同调度中心 (Task & Device Orchestration Center)
    核心特性：
    1. 支持创建多个独立的 Codex 会话任务 (Task Sessions)，各会话状态与日志完全隔离；
    2. 支持单个任务分发给多台设备 (Android + iOS) 并发执行兼容性矩阵测试；
    3. 基于设备级互斥锁 (Device Locks) 实现设备独占与排队调度 (FIFO)；
    4. 采用 ThreadPoolExecutor 进行线程池异步驱动，毫秒级响应。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TaskManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="TaskWorker")
        self.device_locks: Dict[str, threading.Lock] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.active_session_id: Optional[str] = None
        self.session_procs: Dict[str, subprocess.Popen] = {}
        self._session_save_locks: Dict[str, threading.Lock] = {}
        self._session_save_locks_guard = threading.Lock()
        self._load_persisted_sessions()

    def _save_session(self, session_id: str):
        """将单个会话原子化存盘持久化到本地磁盘，保证重启与刷新不丢失"""
        session = self.sessions.get(session_id)
        if not session:
            return

        with self._session_save_locks_guard:
            lock = self._session_save_locks.setdefault(session_id, threading.Lock())

        with lock:
            # 🛡️ 契约式 Generative UI 校验清洗 (借鉴 Vercel Labs json-render 规范)
            if "timeline_blocks" in session and isinstance(session["timeline_blocks"], list):
                session["timeline_blocks"] = [TimelineManager.validate_and_sanitize_block(b) for b in session["timeline_blocks"]]
            target_path = SESSIONS_STORE_DIR / f"{session_id}.json"
            tmp_path = target_path.with_name(f"{target_path.name}.tmp")
            try:
                # 先快照再序列化：避免其他线程并发修改导致写出半截或不一致的 JSON
                snapshot = None
                for _ in range(3):
                    try:
                        snapshot = copy.deepcopy(session)
                        break
                    except RuntimeError:
                        time.sleep(0.01)
                if snapshot is None:
                    raise RuntimeError("会话在快照期间持续被修改")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                # Windows 下目标文件正被读取时 replace 会短暂 PermissionError，稍后重试
                for attempt in range(5):
                    try:
                        os.replace(tmp_path, target_path)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.warning(f"持久化会话 {session_id} 失败: {e}")
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _load_persisted_sessions(self):
        """服务启动时自动从本地磁盘加载所有历史测试会话"""
        files = list(SESSIONS_STORE_DIR.glob("*.json"))
        # 按文件修改时间正序加载，最新的放在最前
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files:
            # 🛡️ 过滤单元测试产生的测试会话文件，杜绝污染正式界面任务列表
            if p.name.startswith("test_") or p.name.startswith("sess_test_") or p.name.startswith("sess_unit_"):
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    sess = json.load(f)
                    sid = sess.get("session_id") or p.stem
                    if "timestamp" not in sess:
                        sess["timestamp"] = p.stat().st_mtime
                    self.sessions[sid] = sess
                    if not self.active_session_id:
                        self.active_session_id = sid
            except Exception as e:
                logger.warning(f"读取历史会话文件 {p.name} 失败: {e}")

        # 若没有任何历史会话，才创建默认欢迎引导会话
        if not self.sessions:
            self._create_default_welcome_session()

    def pause_session(self, session_id: str) -> bool:
        """用户主动暂停测试任务：Windows 底层挂起子进程，状态变更为 PAUSED"""
        session = self.sessions.get(session_id)
        if not session or session.get("status") != "RUNNING":
            return False
        
        proc = self.session_procs.get(session_id)
        if proc and proc.poll() is None:
            try:
                import ctypes
                PROCESS_ALL_ACCESS = 0x1FFFFF
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)
                ctypes.windll.ntdll.NtSuspendProcess(handle)
                ctypes.windll.kernel32.CloseHandle(handle)
                logger.info(f"⏸️ 成功挂起会话 [{session_id}] 进程 (PID: {proc.pid})")
            except Exception as e:
                logger.warning(f"挂起进程异常: {e}")

        session["status"] = "PAUSED"
        for d in session.get("devices", {}).values():
            d["action"] = "⏸️ 任务已暂停"
            d["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏸️ 用户主动暂停了测试任务")
        self._save_session(session_id)
        return True

    def resume_session(self, session_id: str) -> bool:
        """用户主动恢复测试任务：Windows 底层解冻子进程，状态恢复为 RUNNING"""
        session = self.sessions.get(session_id)
        if not session or session.get("status") != "PAUSED":
            return False

        proc = self.session_procs.get(session_id)
        if proc and proc.poll() is None:
            try:
                import ctypes
                PROCESS_ALL_ACCESS = 0x1FFFFF
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)
                ctypes.windll.ntdll.NtResumeProcess(handle)
                ctypes.windll.kernel32.CloseHandle(handle)
                logger.info(f"▶️ 成功恢复会话 [{session_id}] 进程 (PID: {proc.pid})")
            except Exception as e:
                logger.warning(f"恢复进程异常: {e}")

        session["status"] = "RUNNING"
        for d in session.get("devices", {}).values():
            d["action"] = "▶️ 任务恢复执行中"
            d["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ▶️ 用户恢复了测试任务推进")
        self._save_session(session_id)
        return True

    def stop_session(self, session_id: str) -> bool:
        """用户主动彻底停止测试任务：Windows 底层递归强制杀死进程树，终止所有 ADB 管道与后续步骤"""
        session = self.sessions.get(session_id)
        if not session:
            return False

        proc = self.session_procs.get(session_id)
        if proc:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5)
                proc.kill()
                logger.info(f"⏹️ 成功强制终止会话 [{session_id}] 进程树 (PID: {proc.pid})")
            except Exception as e:
                logger.warning(f"终止进程树异常: {e}")
            finally:
                self.session_procs.pop(session_id, None)

        # 2. 强力兜底扫描：彻底杀绝所有关联或可能残留的 run_ai_test.py 进程树，绝无孤儿进程逃逸
        try:
            cmd = f'powershell -Command "Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like \'*run_ai_test.py*\' -and $_.CommandLine -like \'*{session_id}*\' }} | Select-Object -ExpandProperty ProcessId"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            for line in res.stdout.strip().split():
                if line.isdigit():
                    pid = int(line)
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=3)
                    logger.info(f"⏹️ 强力兜底清理测试进程 PID: {pid}")
        except Exception as e:
            logger.warning(f"兜底清理孤儿进程异常: {e}")

        session["status"] = "STOPPED"
        session["is_success"] = False
        session["error_message"] = "用户主动终止了测试任务"
        session["hitl_decision"] = None

        # 3. 彻底释放并中断底层人机协同等待
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

        steps = session.get("plan_steps", [])
        for st in steps:
            if st.get("status") in ["RUNNING", "READY", "PENDING"]:
                st["status"] = "CANCELED"

        for d in session.get("devices", {}).values():
            d["status"] = "STOPPED"
            d["action"] = "⏹️ 用户主动终止"
            d["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹️ 用户主动终止了测试任务，执行已彻底停止")

        self._save_session(session_id)
        return True

    def _get_device_lock(self, device_id: str) -> threading.Lock:
        if device_id not in self.device_locks:
            self.device_locks[device_id] = threading.Lock()
        return self.device_locks[device_id]

    def _create_default_welcome_session(self):
        sess_id = f"sess_{datetime.now().strftime('%m%d_%H%M%S')}_init"
        self.sessions[sess_id] = {
            "session_id": sess_id,
            "title": "系统就绪引导会话",
            "goal": "Autotest AI 移动端多任务平台已就绪。支持单任务多分发与多设备协同测试。",
            "case_name": "welcome_task",
            "test_mode": "local",
            "created_at": datetime.now().strftime("%H:%M:%S"),
            "timestamp": time.time(),
            "status": "COMPLETED",
            "target_devices": ["default"],
            "devices": {
                "default": {
                    "device_id": "default",
                    "model": "系统调度中心",
                    "platform": "Host",
                    "status": "PASS",
                    "step": 1,
                    "max_steps": 1,
                    "action": "系统服务健康就绪",
                    "logs": [
                        f"[{datetime.now().strftime('%H:%M:%S')}] 欢迎使用 Autotest AI 多任务测试平台！",
                        f"[{datetime.now().strftime('%H:%M:%S')}] 您可在左侧随时发起新测试任务，并在对话框上方勾选一台或多台设备协同执行。"
                    ],
                    "report_url": "",
                    "duration": "0.1s"
                }
            },
            "report_url": ""
        }
        self.active_session_id = sess_id
        self._save_session(sess_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """按创建时间戳严格倒序获取所有任务会话概要（确保最新任务永远排在最顶端）"""
        res = []
        all_sessions = list(self.sessions.values())
        all_sessions.sort(key=lambda s: float(s.get("timestamp") or 0), reverse=True)
        for s in all_sessions:
            device_summaries = []
            devices_map = s.get("devices") or {}
            for dev_k, d in devices_map.items():
                if not isinstance(d, dict):
                    continue
                device_summaries.append({
                    "device_id": d.get("device_id") or dev_k,
                    "model": d.get("model") or dev_k,
                    "status": d.get("status") or "IDLE"
                })
            platforms = list(set([d.get("platform", "Android") for d in devices_map.values() if isinstance(d, dict)]))
            if not platforms:
                platforms = ["Android"]
            res.append({
                "session_id": s.get("session_id", ""),
                "title": s.get("title", "未命名任务"),
                "goal": s.get("goal", ""),
                "status": s.get("status", "IDLE"),
                "is_success": s.get("is_success"),
                "created_at": s.get("created_at", ""),
                "timestamp": float(s.get("timestamp") or 0),
                "test_mode": s.get("test_mode", "real"),
                "is_real_device": (s.get("test_mode") == "real"),
                "platforms": platforms,
                "device_count": len(devices_map),
                "devices": device_summaries,
                "report_url": s.get("report_url", "")
            })
        return res

    def rework_session(self, session_id: str, rework_note: str) -> Dict[str, Any]:
        """
        打回返工 (Rework)：携带明确返工要求，状态切回 RUNNING，并在端侧原地执行纠偏与重测
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        turns = MemoryManager.ensure_session_turns(session)
        now_str = datetime.now().strftime("%H:%M:%S")

        if "rework_history" not in session or not isinstance(session["rework_history"], list):
            session["rework_history"] = []
        session["rework_history"].append({
            "timestamp": now_str,
            "rework_note": rework_note
        })

        new_turn_id = len(turns) + 1
        new_turn = MemoryManager.create_turn(new_turn_id, f"打回返工: {rework_note}", is_rework=True, rework_note=rework_note)
        
        turn_steps = [
            {
                "step_id": 1,
                "title": f"返工纠偏：{rework_note[:14]}",
                "desc": f"针对【{rework_note}】原地调整界面状态并执行修正动作",
                "status": "RUNNING"
            },
            {
                "step_id": 2,
                "title": "复核与二次断言",
                "desc": "完成纠偏后校验界面转场并重新生成断言证据",
                "status": "PENDING"
            }
        ]
        new_turn["plan_steps"] = turn_steps
        turns.append(new_turn)

        session["plan_steps"] = turn_steps
        session["status"] = "RUNNING"
        session["is_success"] = None
        session["error_message"] = None

        # 🚀 对标 DeepSeek 连续对话机制：即时向对话流注入返工纠偏提问与新规划
        if "timeline_blocks" not in session or not isinstance(session["timeline_blocks"], list):
            session["timeline_blocks"] = []
        session["timeline_blocks"].append(
            TimelineManager.create_user_block(f"打回返工要求: {rework_note}", turn_id=new_turn_id)
        )
        session["timeline_blocks"].append(
            TimelineManager.create_thought_block(
                duration="1.2s",
                bullets=[
                    {"tag": "返工诉求拆解", "content": f"分析人工返工要求【{rework_note[:24]}】"},
                    {"tag": "原地纠偏策略", "content": "针对未达标项原地微调手势并执行二次断言"}
                ],
                turn_id=new_turn_id,
                is_done=False
            )
        )
        session["timeline_blocks"].append(
            TimelineManager.create_todo_block(turn_steps, turn_id=new_turn_id)
        )

        target_devs = session.get("target_devices", [])
        if not target_devs and "devices" in session:
            target_devs = list(session["devices"].keys())
        for dev_id in target_devs:
            if dev_id in session.get("devices", {}):
                session["devices"][dev_id]["status"] = "QUEUED"
                session["devices"][dev_id]["action"] = f"执行用户返工要求: {rework_note[:16]}..."
                session["devices"][dev_id]["logs"].append(f"[{now_str}] 🔄 [收到打回返工指令]: {rework_note}")
            self.executor.submit(
                self._device_worker,
                session_id,
                dev_id,
                f"返工要求: {rework_note}",
                session.get("case_name", "auto_flow"),
                session.get("test_mode", "real"),
                new_turn_id
            )

        self._save_session(session_id)
        return {"success": True, "session_id": session_id, "turn_id": new_turn_id, "status": "RUNNING"}

    def accept_session(self, session_id: str) -> Dict[str, Any]:
        """
        正式验收通过当前任务并封板归档 (Accept)
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        session["status"] = "COMPLETED"
        session["is_success"] = True
        session["accepted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        turns = MemoryManager.ensure_session_turns(session)
        if turns:
            turns[-1]["status"] = "COMPLETED"
            if not turns[-1].get("conclusion"):
                turns[-1]["conclusion"] = "用户已正式验收通过本次自动化测试交付物，流程封板归档。"

        # 🌟 单一事实源自愈：验收封板时全链路状态 100% 归一化为 COMPLETED
        steps = session.get("plan_steps", [])
        for st in steps:
            st["status"] = "COMPLETED"
            st["error_msg"] = None

        tb = session.get("timeline_blocks", [])
        for card in tb:
            if card.get("type") in ["step_execution", "step_result"]:
                card["status"] = "COMPLETED"
                clean_title = card.get("title", "").replace(" (未通过)", "").replace("验证受阻 ❌", "").replace("验证通过 ✅", "").strip()
                card["title"] = f"{clean_title} 验证通过 ✅"
                card["assertion_result"] = f"阶段断言达成：【{clean_title}】已顺利完成并核验"
                for act in card.get("actions", []):
                    act["status"] = "COMPLETED"
            elif card.get("type") == "todo_list":
                card["status"] = "COMPLETED"
                card["completed_count"] = len(steps)
                card["total_count"] = len(steps)
                card["title"] = f"任务清单 · 全部目标达成 ({len(steps)}/{len(steps)})"
                for it in card.get("items", []):
                    it["status"] = "COMPLETED"

        self.register_deliverables(session_id)
        self._save_session(session_id)
        return {"success": True, "session_id": session_id, "status": "COMPLETED"}

    def register_deliverables(self, session_id: str) -> list:
        """
        全景测试交付物矩阵自动注册与核验 (逐项检查本地物理文件真实存在且非空)
        """
        session = self.sessions.get(session_id)
        if not session:
            return []

        deliverables = []
        # 1. 固化 Pytest 脚本
        solid_file = session.get("solidified_filename")
        if solid_file:
            p = Path("test_cases/generated") / solid_file
            if p.exists() and p.stat().st_size > 0:
                deliverables.append({
                    "id": f"deliv_script_{session_id}",
                    "kind": "script",
                    "title": f"确定性回归用例脚本 ({solid_file})",
                    "path": f"test_cases/generated/{solid_file}",
                    "status": "validated",
                    "size_bytes": p.stat().st_size,
                    "summary": "由 AI 验证成功的操作轨迹自动固化提炼，支持 Pytest 原生回归"
                })

        # 2. HTML 可视化报告
        rep_url = session.get("report_url")
        if rep_url and rep_url.startswith("/reports/"):
            rep_name = rep_url.replace("/reports/", "")
            rep_path = Path("reports") / rep_name
            if rep_path.exists() and rep_path.stat().st_size > 0:
                deliverables.append({
                    "id": f"deliv_report_{session_id}",
                    "kind": "report",
                    "title": f"全景可视化测试报告 ({rep_name})",
                    "path": f"reports/{rep_name}",
                    "url": rep_url,
                    "status": "validated",
                    "size_bytes": rep_path.stat().st_size,
                    "summary": "包含全链路执行指标、耗时分布与断言分析的交互式报告"
                })

        # 3. 关键断言证据截图
        shots_dir = Path("reports/screenshots")
        if shots_dir.exists():
            shots = sorted(shots_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)[:6]
            for idx, s in enumerate(shots):
                if s.stat().st_size > 0:
                    deliverables.append({
                        "id": f"deliv_shot_{session_id}_{idx}",
                        "kind": "screenshot",
                        "title": f"关键步骤断言证据截图 [{s.name}]",
                        "path": str(s).replace("\\", "/"),
                        "url": f"/reports/screenshots/{s.name}",
                        "status": "validated",
                        "size_bytes": s.stat().st_size,
                        "summary": "端侧视觉感知与界面转场验证的真实截屏证据"
                    })

        session["deliverables"] = deliverables
        return deliverables

    def compact_session_context(self, session_id: str) -> Dict[str, Any]:
        """
        一键压缩会话历史上下文 (/compact)
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        res = MemoryManager.compact_session(session)
        self._save_session(session_id)
        return res

    def resolve_decision(self, session_id: str, payload: dict) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        decision_type = payload.get("decision_type", "inject")
        account = payload.get("account", "").strip()
        password = payload.get("password", "").strip()
        sms_code = payload.get("sms_code", "").strip()
        inputs = payload.get("inputs") or {}
        choice = payload.get("choice", "")
        remember = payload.get("remember", False)
        app_key = payload.get("app_key") or session.get("app_package") or session.get("app_label") or session.get("app_filename") or "demo_app"

        if remember and account and password:
            try:
                from core.credential_manager import CredentialManager
                CredentialManager.set_credential(app_key, account, password)
            except Exception as e:
                logger.warning(f"保存凭证失败: {e}")

        # 写入通信文件唤醒子进程
        from pathlib import Path
        import json
        decision_file = BASE_DIR / "scratch" / f"decision_{session_id}.json"
        decision_file.parent.mkdir(parents=True, exist_ok=True)
        decision_file.write_text(json.dumps({
            "status": "RESOLVED",
            "decision_type": decision_type,
            "account": account,
            "password": password,
            "sms_code": sms_code,
            "inputs": inputs,
            "choice": choice,
            "remember": remember
        }, ensure_ascii=False), encoding="utf-8")

        # 恢复状态
        session["status"] = "RUNNING"
        session["hitl_decision"] = None
        for d in session.get("devices", {}).values():
            d["action"] = f"人机协同决策通过 ({decision_type})，恢复执行"
            d["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 人机协同决策完成: {decision_type}，恢复自动化测试")
        self._save_session(session_id)
        return True

    def clarify_session(self, session_id: str, inputs: Dict[str, Any]) -> bool:
        """接收用户在中间区域提交的补充测试参数并继续执行"""
        session = self.sessions.get(session_id)
        if not session:
            return False

        account = inputs.get("account", "访客")
        env = inputs.get("env", "生产")
        session["user_supplement"] = inputs
        session["clarification"] = None # 补充完毕关闭提示

        for dev_id, dev in session["devices"].items():
            dev["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 收到用户补充前置参数: 账号[{account}] 环境[{env}]，继续执行")

        return True

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            target_path = SESSIONS_STORE_DIR / f"{session_id}.json"
            if target_path.exists():
                try:
                    target_path.unlink()
                except Exception as e:
                    logger.warning(f"删除持久化会话文件 {target_path} 失败: {e}")
            if self.active_session_id == session_id:
                self.active_session_id = next(iter(self.sessions.keys()), None)
            return True
        return False

    def _resolve_device_label(self, device_id: str, test_mode: str) -> str:
        if test_mode == "local" or "local" in device_id:
            return "本地免机仿真引擎"
        if "ios" in device_id.lower():
            return "Apple iPhone 15"
        
        # 探测 Android 设备型号
        from core.app_manager import AppManager
        adb_bin = AppManager().adb_bin
        try:
            res = subprocess.run([adb_bin, "-s", device_id, "shell", "getprop", "ro.product.model"], capture_output=True, text=True, timeout=2)
            if res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            logger.debug("忽略异常 @ _resolve_device_label", exc_info=True)
        return f"Android 真机 ({device_id[:8]})"

