# -*- coding: utf-8 -*-
"""scrcpy 推流管理：按需启动、帧率档位切换、失败冷却回退、空闲回收、帧结构与 hub 集成"""
import asyncio

import numpy as np
import pytest

import core.scrcpy_stream as scrcpy_module
import core.screen_stream_hub as hub_module
from core.scrcpy_stream import ScrcpyStream, ScrcpyStreamManager


class FakeStream:
    instances = []

    def __init__(self, adb_bin, device_id, max_fps, fail=False):
        self.device_id, self.max_fps, self.fail, self.stopped = device_id, max_fps, fail, False
        FakeStream.instances.append(self)

    def start(self):
        if self.fail:
            raise RuntimeError("encoder unsupported")

    def stop(self):
        self.stopped = True

    @property
    def alive(self):
        return not self.stopped

    def latest_frame(self, wait=0.0):
        return {"jpeg": b"jpg", "bgr": None, "w": 1080, "h": 2160, "mode": "scrcpy_h264", "time": 0}


@pytest.fixture
def manager(monkeypatch):
    FakeStream.instances = []
    monkeypatch.setattr(scrcpy_module, "BACKEND", "auto")
    monkeypatch.setattr(ScrcpyStreamManager, "enabled", property(lambda self: True))
    monkeypatch.setattr(scrcpy_module, "ScrcpyStream", FakeStream)
    m = ScrcpyStreamManager()
    m._start_reaper = lambda: None
    return m


def test_starts_on_demand_and_reuses_stream(manager):
    assert manager.get_frame("adb", "d1", live=True)["mode"] == "scrcpy_h264"
    manager.get_frame("adb", "d1", live=True)
    assert len(FakeStream.instances) == 1 and FakeStream.instances[0].max_fps == scrcpy_module.LIVE_FPS


def test_fps_tier_change_restarts_stream(manager):
    manager.get_frame("adb", "d1", live=True)
    manager.get_frame("adb", "d1", live=False)
    assert [s.max_fps for s in FakeStream.instances] == [scrcpy_module.LIVE_FPS, scrcpy_module.IDLE_FPS]
    assert FakeStream.instances[0].stopped


def test_start_failure_enters_cooldown_and_returns_none(manager, monkeypatch):
    monkeypatch.setattr(scrcpy_module, "ScrcpyStream", lambda a, d, f: FakeStream(a, d, f, fail=True))
    assert manager.get_frame("adb", "d1", live=True) is None
    assert manager.get_frame("adb", "d1", live=True) is None
    assert len(FakeStream.instances) == 1  # 冷却期内不再反复尝试启动


def test_backend_screencap_disables_scrcpy(monkeypatch):
    monkeypatch.setattr(scrcpy_module, "BACKEND", "screencap")
    assert ScrcpyStreamManager().get_frame("adb", "d1", live=True) is None


def test_idle_streams_are_reaped(manager):
    manager.get_frame("adb", "d1", live=True)
    manager.get_frame("adb", "d2", live=True)
    manager._last_access["d1"] -= scrcpy_module.STREAM_IDLE_STOP_SECONDS + 1
    manager._reap_once()
    assert FakeStream.instances[0].stopped and "d1" not in manager._streams
    assert not FakeStream.instances[1].stopped and "d2" in manager._streams


@pytest.mark.parametrize("decoded_shape,expected", [((960, 480, 3), (1080, 2160)), ((480, 960, 3), (2160, 1080))])
def test_encoded_frame_matches_hub_contract(decoded_shape, expected):
    stream = ScrcpyStream("adb", "d1", 10)
    stream.native_size = (1080, 2160)
    frame = stream._encode(np.zeros(decoded_shape, dtype=np.uint8))
    assert (frame["w"], frame["h"]) == expected
    assert frame["bgr"].shape[1] == scrcpy_module.THUMB_WIDTH and frame["jpeg"][:2] == b"\xff\xd8"


def test_hub_prefers_scrcpy_and_falls_back_to_screencap(monkeypatch):
    hub = hub_module.ScreenStreamHub(adb_bin="adb")
    monkeypatch.setattr(hub_module.scrcpy_manager, "get_frame",
                        lambda adb, dev, live: {"jpeg": b"s", "w": 1, "h": 2, "time": 9e9, "mode": "scrcpy_h264"})
    assert asyncio.run(hub.get_frame("d1", max_age=0.8))["mode"] == "scrcpy_h264"

    hub2 = hub_module.ScreenStreamHub(adb_bin="adb")
    monkeypatch.setattr(hub_module.scrcpy_manager, "get_frame", lambda adb, dev, live: None)
    monkeypatch.setattr(hub_module, "_capture_raw_and_encode_sync",
                        lambda adb, dev: {"jpeg": b"c", "w": 1, "h": 2, "time": 9e9, "mode": "raw_cv2"})
    assert asyncio.run(hub2.get_frame("d1", max_age=0.8))["mode"] == "raw_cv2"
