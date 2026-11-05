# -*- coding: utf-8 -*-
"""真机省电：空闲降频投屏、gzip 开关、稳定检测限帧、稳定帧复用、UI 树指纹复用"""
import base64
import io
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

import core.native_adb_driver as driver_module
import core.screen_stream_hub as hub_module
import web.routers.devices as devices_router
from ai_engine.screen_parser import ScreenParser, SETTLE_MAX_FRAMES
from core import frame_cache
from core.native_adb_driver import NativeADBDriver
from tests.frontend_source import read_frontend_source

XML = ('<?xml version="1.0"?><hierarchy><node text="首页" resource-id="tab_home" class="android.widget.TextView" '
       'clickable="true" bounds="[0,2000][270,2160]"/></hierarchy>')


def _png(text="", status_text="12:00", noise=0):
    img = Image.new("RGB", (540, 1080), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 5), status_text, fill="black")          # 状态栏区域
    draw.text((100, 500), text, fill="black")              # 正文区域
    if noise:
        draw.rectangle((0, 300, 540, 300 + noise * 40), fill=(noise * 37 % 255, 80, 160))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FakeNativeDriver(NativeADBDriver):
    """保留真实 execute_adb（含缓存作废逻辑），仅替换截屏与 dump 计数"""

    def __init__(self, frames):
        self.adb_bin, self.device_id = "adb", "fake_dev"
        self.frames, self.captures, self.dumps = list(frames), 0, 0

    @property
    def page_source(self):
        self.dumps += 1
        return XML

    def get_screenshot_as_base64(self):
        frame = self.frames[min(self.captures, len(self.frames) - 1)]
        self.captures += 1
        return base64.b64encode(frame).decode()


@pytest.fixture(autouse=True)
def _no_real_adb(monkeypatch):
    monkeypatch.setattr(driver_module.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))


def test_strict_fingerprint_ignores_status_bar_but_catches_text_change():
    base = frame_cache.strict_fingerprint(_png("精装"))
    assert base == frame_cache.strict_fingerprint(_png("精装", status_text="12:01"))
    assert base != frame_cache.strict_fingerprint(_png("精装两居"))


def test_ui_tree_reused_when_screen_unchanged_and_redumped_after_input():
    drv = FakeNativeDriver([_png("同一屏")])
    ScreenParser.get_screen_summary(drv)
    ScreenParser.get_screen_summary(drv)
    assert drv.dumps == 1
    drv.execute_adb(["shell", "input", "tap", "1", "2"])
    ScreenParser.get_screen_summary(drv)
    assert drv.dumps == 2
    frame_cache.invalidate(drv)


def test_ui_tree_not_reused_when_screen_changes():
    drv = FakeNativeDriver([_png("A"), _png("B")])
    ScreenParser.get_screen_summary(drv)
    ScreenParser.get_screen_summary(drv)
    assert drv.dumps == 2
    frame_cache.invalidate(drv)


def test_settle_caps_frames_and_next_perception_reuses_last_frame(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    drv = FakeNativeDriver([_png(noise=i) for i in range(1, 10)])  # 画面持续变化，永不稳定
    ScreenParser.wait_for_visual_settling(drv, max_wait=10)
    assert drv.captures == SETTLE_MAX_FRAMES
    ScreenParser.get_screen_summary(drv)
    assert drv.captures == SETTLE_MAX_FRAMES  # 感知直接复用稳定帧，没有再截屏
    frame_cache.invalidate(drv)


def test_settled_frame_is_dropped_after_input_action(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    drv = FakeNativeDriver([_png("x")])
    ScreenParser.wait_for_visual_settling(drv, max_wait=1)
    before = drv.captures
    drv.execute_adb(["shell", "input", "text", "abc"])
    ScreenParser.get_screen_summary(drv)
    assert drv.captures == before + 1
    frame_cache.invalidate(drv)


def test_stream_interval_is_idle_unless_a_session_is_live(monkeypatch):
    sessions = {"s1": {"status": "READY_FOR_REVIEW", "target_devices": ["dev1"], "devices": {}}}
    monkeypatch.setattr(devices_router.task_mgr, "sessions", sessions)
    assert devices_router._stream_interval_for("dev1") == hub_module.STREAM_IDLE_FRAME_INTERVAL
    sessions["s1"]["status"] = "RUNNING"
    assert devices_router._stream_interval_for("dev1") == hub_module.STREAM_FRAME_INTERVAL
    assert devices_router._stream_interval_for("other") == hub_module.STREAM_IDLE_FRAME_INTERVAL


def test_device_gzip_capture_can_be_disabled(monkeypatch):
    monkeypatch.setattr(hub_module, "DEVICE_GZIP_CAPTURE", False)
    assert [m for m, _ in hub_module._raw_capture_variants("devX")] == ["raw_cv2"]
    monkeypatch.setattr(hub_module, "DEVICE_GZIP_CAPTURE", True)
    assert [m for m, _ in hub_module._raw_capture_variants("devX")][0] == "raw_gzip_cv2"


def test_frontend_pauses_screen_polling_when_idle():
    src = read_frontend_source()
    assert "function isScreenIdlePaused()" in src
    assert src.count("isScreenIdlePaused()") >= 3  # 定义 + 画中画循环 + 画布自动同步
