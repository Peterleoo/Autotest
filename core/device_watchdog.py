# -*- coding: utf-8 -*-
"""
真机执行看门狗与自愈引擎 (Device Watchdog & Self-Healing Engine)
借鉴 DeepSeek Super-agent (DSH) 原型设计：
1. 轻量非侵入式心跳契约 (Heartbeat Contract)；
2. 两级异常诊断探针 (Two-Stage Anomaly Probe)；
3. 自动化黑匣子快照与三级渐进自愈策略 (Self-Healing Actions)；
4. 杜绝单点阻塞导致整套测试资产殉爆。
"""

import os
import re
import time
import shutil
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List

logger = logging.getLogger("DeviceWatchdog")

DEVICE_STATE_ONLINE = "device"
DEVICE_STATE_ABSENT = "absent"
DEVICE_STATE_UNKNOWN = "unknown"

ADB_CMD_TIMEOUT = 5.0          # 单条 adb shell 诊断指令超时（投屏占用通道时 2s 过短易误判）
ADB_DEVICES_TIMEOUT = 8.0      # adb devices / reconnect 超时
RECONNECT_WAIT_TIMEOUT = 15.0  # 单设备重连后等待恢复上限
OFFLINE_CONFIRM_DELAY = 1.5    # 判定离线前的复核间隔
DEFAULT_WATCHDOG_TIMEOUT = 180.0  # 无日志输出判定假死阈值（大模型推理/页面加载常超 60s，过短会误杀测试）


def parse_device_state(devices_output: str, device_id: str) -> str:
    """从 `adb devices` 输出中精确解析指定设备状态（逐行精确匹配序列号，杜绝子串误判）"""
    for line in devices_output.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[0] == device_id:
            return parts[1]
    return DEVICE_STATE_ABSENT


class DeviceWatchdog:
    def __init__(
        self,
        session_id: str,
        device_id: str,
        target_package: Optional[str] = None,
        timeout_seconds: float = 60.0,
        adb_bin: Optional[str] = None,
        on_heal_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        get_session_status: Optional[Callable[[], str]] = None
    ):
        self.session_id = session_id
        self.device_id = device_id or "default"
        self.target_package = target_package or ""
        self.timeout_seconds = max(0.1, timeout_seconds)
        self.adb_bin = adb_bin or self._resolve_adb()
        self.on_heal_event = on_heal_event
        self.get_session_status = get_session_status

        self.last_heartbeat = time.time()
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.supervised_proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.heal_history: List[Dict[str, Any]] = []

    def _resolve_adb(self) -> str:
        adb = shutil.which("adb")
        if adb:
            return adb
        sdk_root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if sdk_root:
            cand = Path(sdk_root) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
            if cand.exists():
                return str(cand)
        return "adb"

    def feed_heartbeat(self, context_hint: str = ""):
        """喂狗刷新心跳时间戳"""
        with self.lock:
            self.last_heartbeat = time.time()
            if context_hint:
                logger.debug(f"🐕‍🦺 [Watchdog Heartbeat] [{self.session_id}] 心跳喂狗: {context_hint[:60]}")

    def start(self, proc: Optional[subprocess.Popen] = None):
        """启动看门狗异步守护线程"""
        with self.lock:
            self.running = True
            self.supervised_proc = proc
            self.last_heartbeat = time.time()
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name=f"Watchdog-{self.session_id}-{self.device_id}",
                daemon=True
            )
            self.monitor_thread.start()
            logger.info(f"🐕‍🦺 [Watchdog] 启动真机守护: 设备 [{self.device_id}], 超时阈值: {self.timeout_seconds}s")

    def stop(self):
        """停止看门狗"""
        with self.lock:
            self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
            logger.info(f"🐕‍🦺 [Watchdog] 已安全停止真机守护 [{self.session_id}]")

    def _monitor_loop(self):
        """核心监控循环"""
        sleep_interval = min(0.3, max(0.05, self.timeout_seconds / 3))
        while self.running:
            time.sleep(sleep_interval)
            if not self.running:
                break

            # 🛡️ 智能避让：如果处于人机协同状态（等待用户输入验证码或审批），挂起超时计数
            if self.get_session_status:
                try:
                    cur_status = self.get_session_status()
                    if cur_status in ["WAITING_USER_INPUT", "AWAITING_USER_INPUT", "PAUSED", "STOPPED", "CANCELLED"]:
                        with self.lock:
                            self.last_heartbeat = time.time()
                        continue
                except Exception:
                    logger.debug("忽略异常 @ _monitor_loop", exc_info=True)

            # 检查子进程是否已自然退出
            if self.supervised_proc and self.supervised_proc.poll() is not None:
                break

            # 检查是否超时
            elapsed = time.time() - self.last_heartbeat
            if elapsed > self.timeout_seconds:
                logger.warning(f"⚠️ 🐕‍🦺 [Watchdog Timeout] 触发超时警戒！{elapsed:.1f}s 未收到心跳，启动两级诊断与自愈...")
                self._trigger_diagnosis_and_healing(elapsed)
                # 自愈后重置心跳，防止同一异常暴风雨式重复触发
                with self.lock:
                    self.last_heartbeat = time.time()

    def _trigger_diagnosis_and_healing(self, elapsed: float):
        """执行两级异常诊断与自愈推进"""
        diag = self.diagnose_anomaly()
        heal_action = "none"
        heal_success = False
        message = ""

        # Level 1 诊断与自愈分流
        anomaly_type = diag.get("anomaly_type", "UNKNOWN_HANG")

        if anomaly_type == "DEVICE_OFFLINE":
            # ⚠️ 绝不 kill-server：那会断开本机所有设备、投屏与正在执行的 ADB 指令，反而制造掉线
            heal_action = "reconnect_device"
            heal_success = self._reconnect_device()
            message = (
                f"检测到真机 [{self.device_id}] 掉线 ({diag.get('device_state')})，已对该设备单独重连"
                + ("成功" if heal_success else "失败，请检查 USB 连接与调试授权")
            )

        elif anomaly_type == "ADB_UNRESPONSIVE":
            # ADB 通道繁忙/超时无法判定设备状态：不做任何破坏性动作，等待下一轮心跳复核
            heal_action = "observe_only"
            message = "ADB 通道响应超时，暂无法判定真机状态，本轮不做干预以免误伤连接"

        elif anomaly_type == "SCREEN_OFF":
            heal_action = "wake_and_unlock"
            message = "检测到真机屏幕意外熄屏休眠，已自动发送唤醒按键并上滑解锁"
            self._run_adb_shell(["input", "keyevent", "224"])
            time.sleep(0.3)
            self._run_adb_shell(["input", "swipe", "500", "1500", "500", "500", "300"])
            heal_success = True

        elif anomaly_type == "APP_CRASH_OR_ANR":
            heal_action = "dismiss_anr_and_relaunch"
            focus = diag.get("current_focus", "")
            message = f"检测到目标应用崩溃或出现 ANR 无响应弹窗 ({focus})，已自动清理弹窗并重新拉起前台"
            self._run_adb_shell(["input", "keyevent", "4"])
            time.sleep(0.3)
            if self.target_package:
                self._run_adb_shell(["monkey", "-p", self.target_package, "-c", "android.intent.category.LAUNCHER", "1"])
            heal_success = True

        else:
            # 进程假死或长阻塞，策略 C：终止假死子进程
            heal_action = "terminate_hung_process"
            message = f"子进程执行处于未响应挂起状态 (耗时已超 {elapsed:.0f}s)，看门狗主动终止假死子任务以释放通道"
            if self.supervised_proc and self.supervised_proc.poll() is None:
                try:
                    self.supervised_proc.terminate()
                    time.sleep(0.3)
                    if self.supervised_proc.poll() is None:
                        self.supervised_proc.kill()
                    heal_success = True
                except Exception as e:
                    logger.error(f"终止假死子进程失败: {e}")

        # Level 2 黑匣子证据固化
        evidence_file = self._capture_blackbox_evidence(anomaly_type)

        event_record = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "elapsed_seconds": round(elapsed, 1),
            "anomaly_type": anomaly_type,
            "diagnosis": diag,
            "heal_action": heal_action,
            "heal_success": heal_success,
            "message": message,
            "evidence_screenshot": evidence_file
        }
        self.heal_history.append(event_record)
        logger.info(f"🐕‍🦺 [Watchdog Healed] 自愈完成: {anomaly_type} -> {heal_action} ({message})")

        if self.on_heal_event:
            try:
                self.on_heal_event(event_record)
            except Exception as e:
                logger.error(f"看门狗回调通知异常: {e}")

    def diagnose_anomaly(self) -> Dict[str, Any]:
        """两级静态探针：毫秒级探测真机物理/系统状态"""
        # mock 设备直接短路判断为 EXECUTION_HANG，避免真实 ADB 等待
        if "mock" in self.device_id.lower():
            return {"anomaly_type": "EXECUTION_HANG", "detail": "模拟环境假死测试"}

        # 1. 检查物理设备连接状态（区分"确实离线"与"ADB 繁忙超时"，并二次复核防误判）
        state = self._confirmed_device_state()
        if state == DEVICE_STATE_UNKNOWN:
            return {"anomaly_type": "ADB_UNRESPONSIVE", "device_state": state}
        if state != DEVICE_STATE_ONLINE:
            return {"anomaly_type": "DEVICE_OFFLINE", "device_state": state}

        # 2. 检查屏幕状态
        power_out = self._run_adb_shell(["dumpsys", "power"])
        if "mWakefulness=Asleep" in power_out or "Display Power: state=OFF" in power_out:
            return {"anomaly_type": "SCREEN_OFF", "raw": "Display is asleep"}

        # 3. 检查当前焦点窗口判断是否 ANR / Crash
        focus_out = self._run_adb_shell(["dumpsys", "window", "windows"])
        crash_keywords = ["Application Not Responding", "CrashDialog", "aerr", "ANR", "stopped", "停止运行", "无响应"]
        for kw in crash_keywords:
            if kw.lower() in focus_out.lower():
                return {"anomaly_type": "APP_CRASH_OR_ANR", "current_focus": kw}

        # 4. 检查是否退到了桌面
        act_out = self._run_adb_shell(["dumpsys", "activity", "activities"])
        if "Launcher" in act_out and self.target_package and self.target_package not in act_out[:1000]:
            return {"anomaly_type": "APP_IN_BACKGROUND", "current_focus": "Launcher"}

        return {"anomaly_type": "EXECUTION_HANG", "detail": "真机在线且屏幕点亮，子任务逻辑或网络阻塞无响应"}

    def _capture_blackbox_evidence(self, anomaly_type: str) -> Optional[str]:
        """抓取黑匣子现场快照截图"""
        if "mock" in self.device_id.lower():
            return None
        evidence_dir = Path("outputs") / "evidence" / self.session_id
        try:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            filename = f"watchdog_{anomaly_type.lower()}_{ts}.png"
            dest_path = evidence_dir / filename
            remote_tmp = f"/sdcard/wd_shot_{ts}.png"
            self._run_adb_shell(["screencap", "-p", remote_tmp])
            pull_res = self._run_adb_cmd(["pull", remote_tmp, str(dest_path)])
            self._run_adb_shell(["rm", remote_tmp])
            if dest_path.exists():
                return f"/outputs/evidence/{self.session_id}/{filename}"
        except Exception as e:
            logger.debug(f"快照固化略过: {e}")
        return None

    def _query_device_state(self) -> str:
        """查询目标设备在 `adb devices` 中的精确状态；命令超时/出错时返回 unknown 而非误判离线"""
        try:
            res = subprocess.run(
                [self.adb_bin, "devices"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=ADB_DEVICES_TIMEOUT, encoding="utf-8", errors="ignore"
            )
        except Exception as e:
            logger.warning(f"🐕‍🦺 [Watchdog] adb devices 查询失败，视为状态未知: {e}")
            return DEVICE_STATE_UNKNOWN
        if res.returncode != 0:
            return DEVICE_STATE_UNKNOWN
        return parse_device_state(res.stdout or "", self.device_id)

    def _confirmed_device_state(self) -> str:
        """非在线状态需间隔复核一次，避免 USB 瞬时抖动被当成掉线"""
        state = self._query_device_state()
        if state == DEVICE_STATE_ONLINE:
            return state
        time.sleep(OFFLINE_CONFIRM_DELAY)
        return self._query_device_state()

    def _reconnect_device(self) -> bool:
        """仅针对目标设备重连并等待恢复，不影响同机其他设备与 ADB 服务"""
        self._run_adb_cmd(["reconnect"], timeout=ADB_DEVICES_TIMEOUT)
        self._run_adb_cmd(["wait-for-device"], timeout=RECONNECT_WAIT_TIMEOUT)
        return self._query_device_state() == DEVICE_STATE_ONLINE

    def _run_adb_cmd(self, args: List[str], timeout: float = ADB_CMD_TIMEOUT) -> str:
        if "mock" in self.device_id.lower():
            return ""
        cmd = [self.adb_bin]
        if self.device_id and self.device_id not in ["default"]:
            cmd.extend(["-s", self.device_id])
        cmd.extend(args)
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout, encoding="utf-8", errors="ignore")
            return res.stdout or ""
        except Exception as e:
            return f"ERROR: {e}"

    def _run_adb_shell(self, args: List[str]) -> str:
        return self._run_adb_cmd(["shell"] + args)
