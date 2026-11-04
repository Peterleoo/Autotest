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
