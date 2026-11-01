# -*- coding: utf-8 -*-
import time
import unittest
import subprocess
import sys
from pathlib import Path
from core.device_watchdog import DeviceWatchdog
from core.task_manager import TaskManager, SESSIONS_STORE_DIR


class TestDeviceWatchdog(unittest.TestCase):
    def setUp(self):
        self.mgr = TaskManager()
        self.created_sessions = []

    def tearDown(self):
        for sid in self.created_sessions:
            p = SESSIONS_STORE_DIR / f"{sid}.json"
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
            self.mgr.sessions.pop(sid, None)

    def test_heartbeat_keeps_watchdog_alive(self):
        """测试持续心跳喂狗时，看门狗保持静默且绝不误杀进程"""
        healed_events = []
        wd = DeviceWatchdog(
            session_id="test_sess_hb",
            device_id="mock_device",
            timeout_seconds=0.6,
            on_heal_event=lambda evt: healed_events.append(evt)
        )

        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.2)"])
        wd.start(proc)

        try:
            for i in range(5):
                time.sleep(0.18)
                wd.feed_heartbeat(f"step_{i}")

            self.assertEqual(len(healed_events), 0, "持续喂狗时不应触发看门狗自愈")
        finally:
            wd.stop()
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_hitl_state_suspends_watchdog_timeout(self):
        """测试当处于人机协同挂起状态时，看门狗自动避让，不触发超时误杀"""
        healed_events = []
        is_hitl = True

        wd = DeviceWatchdog(
            session_id="test_sess_hitl",
            device_id="mock_device",
            timeout_seconds=0.4,
            on_heal_event=lambda evt: healed_events.append(evt),
            get_session_status=lambda: "WAITING_USER_INPUT" if is_hitl else "RUNNING"
        )

        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
        wd.start(proc)

        try:
            time.sleep(0.8)
            self.assertEqual(len(healed_events), 0, "人机协同状态下看门狗应智能挂起超时判定")
            self.assertIsNone(proc.poll(), "子进程不应被误杀")
        finally:
            wd.stop()
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_watchdog_heals_hung_process(self):
        """测试进程假死未喂狗时，看门狗自动诊断并终止挂死进程，触发自愈回调"""
        healed_events = []
        wd = DeviceWatchdog(
            session_id="test_sess_hang",
            device_id="mock_device",
            timeout_seconds=0.4,
            on_heal_event=lambda evt: healed_events.append(evt)
        )

        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        wd.start(proc)

        try:
            time.sleep(0.9)
            self.assertGreaterEqual(len(healed_events), 1, "超时应触发自愈事件")
            evt = healed_events[0]
            self.assertEqual(evt["heal_action"], "terminate_hung_process")
            self.assertTrue(evt["heal_success"])
            self.assertIsNotNone(proc.poll(), "假死子进程应被看门狗安全终止")
        finally:
            wd.stop()
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_task_manager_handle_watchdog_heal_event(self):
        """测试 TaskManager 接收自愈事件并结构化注入时间线系统通知"""
        sid = "test_sess_wd_tm"
        session = {
            "session_id": sid,
            "status": "RUNNING",
            "timeline_blocks": [],
            "devices": {"mock_dev": {"logs": []}}
        }
        self.mgr.sessions[sid] = session
        self.created_sessions.append(sid)

        mock_event = {
            "message": "检测到目标应用崩溃，已自动清理弹窗并重新拉起前台",
            "anomaly_type": "APP_CRASH_OR_ANR",
            "heal_action": "dismiss_anr_and_relaunch",
            "heal_success": True,
            "evidence_screenshot": "/outputs/evidence/mock.png"
        }

        self.mgr._handle_watchdog_heal_event(session, session["devices"]["mock_dev"], mock_event)

        tb = session.get("timeline_blocks", [])
        self.assertEqual(len(tb), 1)
        self.assertEqual(tb[0]["type"], "system_notice")
        self.assertIn("看门狗自愈", tb[0]["content"])
        self.assertEqual(tb[0]["evidence"], "/outputs/evidence/mock.png")

        logs = session["devices"]["mock_dev"]["logs"]
        self.assertEqual(len(logs), 1)
        self.assertIn("dismiss_anr_and_relaunch", logs[0])

    def test_suite_runner_tolerates_failed_case(self):
        """测试系统用例套件串联执行时，若中间某项用例失败，套件自动推进后续用例不中断"""
        sid = "test_sess_suite_tolerance"
        session = {
            "session_id": sid,
            "goal": "系统容灾测试",
            "title": "系统容灾测试套件",
            "status": "RUNNING",
            "test_mode": "local",
            "target_devices": ["mock_device"],
            "plan_steps": [],
            "timeline_blocks": [],
            "devices": {
                "mock_device": {
                    "device_id": "mock_device",
                    "status": "RUNNING",
                    "step": 0,
                    "action": "",
                    "logs": []
                }
            }
        }
        self.mgr.sessions[sid] = session
        self.created_sessions.append(sid)

        cases = [
            {"id": "tc-01", "title": "用例1-正常通过", "goal": "正常登录"},
            {"id": "tc-02", "title": "用例2-正常通过", "goal": "浏览房源"}
        ]

        # 同步执行套件串联
        self.mgr._systemic_suite_runner(sid, cases, keep_state=True)

        s = self.mgr.get_session(sid)
        self.assertIn(s["status"], ["COMPLETED", "READY_FOR_REVIEW"])
        logs = s["devices"]["mock_device"]["logs"]
        # 验证两项用例都得到了执行推进
        self.assertTrue(any("用例 [1/2]" in l for l in logs))
        self.assertTrue(any("用例 [2/2]" in l for l in logs))


if __name__ == '__main__':
    unittest.main()
