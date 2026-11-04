# -*- coding: utf-8 -*-
"""真机连接稳定性：看门狗不得因 ADB 繁忙误判掉线、绝不 kill-server；投屏单次抖动不断流；设备列表失败不缓存"""
import asyncio
import subprocess
from types import SimpleNamespace

import pytest

import core.device_watchdog as wd_mod
import core.screen_stream_hub as hub_mod
from core.device_watchdog import DeviceWatchdog, parse_device_state

DEV = "ABC123"
DEVICES_HEADER = "List of devices attached\n"


# ---------------------------------------------------------------- parse_device_state

@pytest.mark.parametrize("output,expected", [
    (DEVICES_HEADER + "ABC123\tdevice\n", "device"),
    (DEVICES_HEADER + "ABC123\toffline\n", "offline"),
    (DEVICES_HEADER + "ABC123\tunauthorized\n", "unauthorized"),
    (DEVICES_HEADER, "absent"),
    (DEVICES_HEADER + "ABC1234\tdevice\n", "absent"),  # 序列号子串不得误判为在线
])
def test_parse_device_state(output, expected):
    assert parse_device_state(output, DEV) == expected


# ---------------------------------------------------------------- watchdog

class FakeAdb:
    """按脚本返回 `adb devices` 结果，记录全部 adb 调用"""

    def __init__(self, devices_results):
        self.devices_results = list(devices_results)
        self.calls = []

    def __call__(self, cmd, *args, **kwargs):
        self.calls.append(cmd)
        if cmd[1:] == ["devices"]:
            nxt = self.devices_results.pop(0) if len(self.devices_results) > 1 else self.devices_results[0]
            if isinstance(nxt, Exception):
                raise nxt
            return SimpleNamespace(returncode=0, stdout=nxt)
        return SimpleNamespace(returncode=0, stdout="mWakefulness=Awake\n")

    def flat_args(self):
        return [a for c in self.calls for a in c]


@pytest.fixture
def watchdog(monkeypatch):
    monkeypatch.setattr(wd_mod, "OFFLINE_CONFIRM_DELAY", 0)
    w = DeviceWatchdog(session_id="t", device_id=DEV, adb_bin="adb")
    monkeypatch.setattr(w, "_capture_blackbox_evidence", lambda *_: None)
    return w


def test_adb_timeout_is_not_treated_as_offline(watchdog, monkeypatch):
    fake = FakeAdb([subprocess.TimeoutExpired("adb", 8)])
    monkeypatch.setattr(wd_mod.subprocess, "run", fake)
    events = []
    watchdog.on_heal_event = events.append

    watchdog._trigger_diagnosis_and_healing(200)

    assert events[0]["anomaly_type"] == "ADB_UNRESPONSIVE"
    assert events[0]["heal_action"] == "observe_only"
    assert "kill-server" not in fake.flat_args()


def test_transient_absence_is_rechecked(watchdog, monkeypatch):
    fake = FakeAdb([DEVICES_HEADER, DEVICES_HEADER + f"{DEV}\tdevice\n"])
    monkeypatch.setattr(wd_mod.subprocess, "run", fake)

    diag = watchdog.diagnose_anomaly()

    assert diag["anomaly_type"] != "DEVICE_OFFLINE"


def test_confirmed_offline_reconnects_single_device_without_kill_server(watchdog, monkeypatch):
    # 两次复核均离线 -> 重连后恢复在线
    fake = FakeAdb([DEVICES_HEADER + f"{DEV}\toffline\n", DEVICES_HEADER + f"{DEV}\toffline\n",
                    DEVICES_HEADER + f"{DEV}\tdevice\n"])
    monkeypatch.setattr(wd_mod.subprocess, "run", fake)
    events = []
    watchdog.on_heal_event = events.append

    watchdog._trigger_diagnosis_and_healing(200)

    evt = events[0]
    assert evt["anomaly_type"] == "DEVICE_OFFLINE"
    assert evt["heal_action"] == "reconnect_device"
    assert evt["heal_success"] is True
    assert ["adb", "-s", DEV, "reconnect"] in fake.calls
    assert "kill-server" not in fake.flat_args()
    assert "start-server" not in fake.flat_args()


def test_default_watchdog_timeout_tolerates_slow_llm_turns():
    assert wd_mod.DEFAULT_WATCHDOG_TIMEOUT >= 120


# ---------------------------------------------------------------- screen stream hub

def _frame(tag):
    return {"jpeg": tag, "bgr": None, "time": 0.0}


def test_hub_keeps_last_frame_on_transient_failure(monkeypatch):
    hub = hub_mod.ScreenStreamHub(adb_bin="adb")
    results = [_frame(b"f1"), None, None, None]
    monkeypatch.setattr(hub_mod, "_capture_raw_and_encode_sync", lambda *_: results.pop(0))

    async def run():
        first = await hub.get_frame(DEV, max_age=0)
        second = await hub.get_frame(DEV, max_age=0)   # 失败 1/3 -> 沿用上一帧
        third = await hub.get_frame(DEV, max_age=0)    # 失败 2/3 -> 沿用上一帧
        fourth = await hub.get_frame(DEV, max_age=0)   # 失败 3/3 -> 判定断连
        fifth = await hub.get_frame(DEV, max_age=0)    # 熔断期内直接返回 None
        return first, second, third, fourth, fifth

    first, second, third, fourth, fifth = asyncio.run(run())
    assert first["jpeg"] == b"f1"
    assert second["jpeg"] == b"f1" and third["jpeg"] == b"f1"
    assert fourth is None and fifth is None
    assert DEV not in hub._cache


def test_hub_success_resets_failure_count(monkeypatch):
    hub = hub_mod.ScreenStreamHub(adb_bin="adb")
    results = [_frame(b"a"), None, None, _frame(b"b"), None, None]
    monkeypatch.setattr(hub_mod, "_capture_raw_and_encode_sync", lambda *_: results.pop(0))

    async def run():
        return [await hub.get_frame(DEV, max_age=0) for _ in range(6)]

    frames = asyncio.run(run())
    assert all(f is not None for f in frames)
    assert frames[-1]["jpeg"] == b"b"


def test_stream_interval_leaves_adb_idle_window():
    assert hub_mod.STREAM_FRAME_INTERVAL >= 0.5
    assert hub_mod.RAW_CAPTURE_TIMEOUT > 3


# ---------------------------------------------------------------- /api/devices

def test_device_list_failure_is_not_cached(monkeypatch):
    import web.routers.devices as app_mod

    cached = {"android_devices": [{"id": DEV}], "ios_node": {}}
    monkeypatch.setitem(app_mod._DEVICE_CACHE, "data", cached)
    monkeypatch.setitem(app_mod._DEVICE_CACHE, "timestamp", 0.0)

    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired("adb", 8)

    monkeypatch.setattr(app_mod.subprocess, "run", boom)

    result = asyncio.run(app_mod.get_devices(force=True))

    assert result is cached
    assert app_mod._DEVICE_CACHE["timestamp"] == 0.0


def test_device_list_failure_without_cache_returns_empty(monkeypatch):
    import web.routers.devices as app_mod

    monkeypatch.setitem(app_mod._DEVICE_CACHE, "data", None)
    monkeypatch.setitem(app_mod._DEVICE_CACHE, "timestamp", 0.0)
    monkeypatch.setattr(app_mod.subprocess, "run",
                        lambda *_a, **_k: SimpleNamespace(returncode=1, stdout="", stderr="daemon not running"))

    result = asyncio.run(app_mod.get_devices(force=True))

    assert result["android_devices"] == []
    assert app_mod._DEVICE_CACHE["data"] is None


@pytest.mark.parametrize("fmt,hub_method", [("jpeg", "get_jpeg_bytes"), ("png", "get_png_bytes")])
def test_screenshot_endpoint_reuses_frames_within_stream_interval(monkeypatch, fmt, hub_method):
    """前端画中画按 /screenshot 轮询：后端必须按 STREAM_FRAME_INTERVAL 复用帧，防止任何客户端把 ADB 通道打满"""
    import web.routers.devices as dev_mod

    seen = {}

    async def fake_get(device_id, max_age):
        seen["max_age"] = max_age
        return b"img"

    monkeypatch.setattr(dev_mod, "resolve_target_device_id", lambda _d: DEV)
    monkeypatch.setattr(dev_mod.screen_stream_hub, hub_method, fake_get)

    resp = asyncio.run(dev_mod.get_device_screenshot(device_id=DEV, format=fmt))

    assert resp.status_code == 200
    assert seen["max_age"] >= hub_mod.STREAM_FRAME_INTERVAL


def test_pip_loop_is_throttled_and_pauses_when_hidden():
    from tests.frontend_source import read_frontend_source

    html = read_frontend_source()
    loop = html[html.index("function runPipStreamLoop()"):html.index("function triggerPipImmediateRefresh()")]
    assert "setTimeout(runPipStreamLoop, 40)" not in loop
    assert "document.hidden" in loop
    assert "const PIP_FRAME_INTERVAL_MS = 800;" in html


# ---------------------------------------------------------------- 端侧 gzip 压缩采集

def _fake_raw_frame(w=64, h=128):
    import struct as _struct
    return _struct.pack("<IIII", w, h, 1, 0) + bytes([120]) * (w * h * 4)


class FakeCapture:
    """按命令返回预设的 exec-out 输出，记录调用的抓屏命令"""

    def __init__(self, outputs):
        self.outputs = outputs
        self.cmds = []

    def __call__(self, cmd, *a, **k):
        shell_cmd = cmd[-1] if cmd[-2] == "exec-out" else " ".join(cmd[cmd.index("exec-out") + 1:])
        self.cmds.append(shell_cmd)
        return SimpleNamespace(returncode=0, stdout=self.outputs.get(shell_cmd, b""))


@pytest.fixture
def clean_gzip_state(monkeypatch):
    if not hub_mod.HAS_OPENCV:
        pytest.skip("需要 OpenCV")
    monkeypatch.setattr(hub_mod, "_GZIP_UNSUPPORTED", set())


def test_capture_prefers_gzip_compressed_raw(monkeypatch, clean_gzip_state):
    import gzip as _gzip
    fake = FakeCapture({"screencap | gzip -1": _gzip.compress(_fake_raw_frame(), 1)})
    monkeypatch.setattr(hub_mod.subprocess, "run", fake)

    frame = hub_mod._capture_raw_and_encode_sync("adb", DEV)

    assert frame["mode"] == "raw_gzip_cv2"
    assert (frame["w"], frame["h"]) == (64, 128)
    assert fake.cmds == ["screencap | gzip -1"]


def test_capture_falls_back_and_remembers_when_gzip_missing(monkeypatch, clean_gzip_state):
    fake = FakeCapture({"screencap | gzip -1": b"/system/bin/sh: gzip: not found\n", "screencap": _fake_raw_frame()})
    monkeypatch.setattr(hub_mod.subprocess, "run", fake)

    first = hub_mod._capture_raw_and_encode_sync("adb", DEV)
    second = hub_mod._capture_raw_and_encode_sync("adb", DEV)

    assert first["mode"] == second["mode"] == "raw_cv2"
    assert fake.cmds == ["screencap | gzip -1", "screencap", "screencap"]  # 第二帧不再白跑 gzip


def test_truncated_gzip_does_not_permanently_disable_compression(monkeypatch, clean_gzip_state):
    import gzip as _gzip
    truncated = _gzip.compress(_fake_raw_frame(), 1)[:50]  # 模拟 USB 中途断开导致的截断
    fake = FakeCapture({"screencap | gzip -1": truncated, "screencap": _fake_raw_frame()})
    monkeypatch.setattr(hub_mod.subprocess, "run", fake)

    frame = hub_mod._capture_raw_and_encode_sync("adb", DEV)

    assert frame["mode"] == "raw_cv2"
    assert DEV not in hub_mod._GZIP_UNSUPPORTED


# ---------------------------------------------------------------- 测试数据隔离

def test_tests_never_write_to_real_session_store():
    """测试产生的会话必须进临时目录，不能出现在用户侧边栏任务列表"""
    from core.task_common import BASE_DIR, SESSIONS_STORE_DIR, TEST_SUITES_STORE_DIR

    assert SESSIONS_STORE_DIR.resolve() != (BASE_DIR / "data" / "sessions").resolve()
    assert TEST_SUITES_STORE_DIR.resolve() != (BASE_DIR / "data" / "test_suites").resolve()


def test_no_hardcoded_session_paths_left():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    offenders = [
        str(p.relative_to(root))
        for d in ("core", "ai_engine", "web")
        for p in (root / d).rglob("*.py")
        if 'Path("data/sessions")' in p.read_text(encoding="utf-8", errors="ignore")
    ] + (["run_ai_test.py"] if 'Path("data/sessions")' in (root / "run_ai_test.py").read_text(encoding="utf-8") else [])
    assert offenders == []
