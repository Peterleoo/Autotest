# -*- coding: utf-8 -*-
"""AI 子进程取帧：优先从 Web 服务取推流最新帧，服务不可达时回退本地截屏且不再重试"""
import asyncio
import io

import pytest

import core.native_adb_driver as driver_module
import web.routers.devices as devices_router
from core.native_adb_driver import NativeADBDriver

PNG = b"\x89PNG\r\n\x1a\n" + b"stream-frame"


def _driver():
    drv = object.__new__(NativeADBDriver)
    drv.adb_bin, drv.device_id = "adb", "dev1"
    return drv


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_uses_screen_server_frame_with_fresh_flag(monkeypatch):
    monkeypatch.setenv("AUTOTEST_SCREEN_SERVER", "http://127.0.0.1:9999")
    urls = []
    monkeypatch.setattr(driver_module.urllib.request, "urlopen",
                        lambda url, timeout: urls.append(url) or _Resp(PNG))
    assert _driver().get_screenshot_as_png() == PNG
    assert urls == ["http://127.0.0.1:9999/api/devices/dev1/screenshot?format=png&fresh=1"]


def test_falls_back_to_local_capture_and_stops_retrying(monkeypatch):
    monkeypatch.setenv("AUTOTEST_SCREEN_SERVER", "http://127.0.0.1:9999")
    calls = []

    def boom(url, timeout):
        calls.append(url)
        raise OSError("connection refused")

    monkeypatch.setattr(driver_module.urllib.request, "urlopen", boom)
    monkeypatch.setattr("core.screen_stream_hub._capture_raw_and_encode_sync",
                        lambda adb, dev: {"jpeg": b"local-jpeg", "bgr": None})
    drv = _driver()
    assert drv.get_screenshot_as_png() == b"local-jpeg"
    assert drv.get_screenshot_as_png() == b"local-jpeg"
    assert len(calls) == 1  # 失败一次后本驱动不再请求服务


def test_screen_server_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("AUTOTEST_SCREEN_SERVER", "off")
    monkeypatch.setattr(driver_module.urllib.request, "urlopen",
                        lambda *a, **k: pytest.fail("不应请求投屏服务"))
    assert _driver()._screenshot_from_screen_server() is None


@pytest.mark.parametrize("fresh", [True, False])
def test_screenshot_endpoint_fresh_bypasses_frame_cache(monkeypatch, fresh):
    seen = {}

    async def fake_png(dev, max_age):
        seen["max_age"] = max_age
        return PNG

    monkeypatch.setattr(devices_router, "resolve_target_device_id", lambda d: "dev1")
    monkeypatch.setattr(devices_router.screen_stream_hub, "get_png_bytes", fake_png)
    monkeypatch.setattr(devices_router, "_stream_interval_for", lambda d: 3.0)
    resp = asyncio.run(devices_router.get_device_screenshot("dev1", format="png", fresh=fresh))
    assert resp.body == PNG
    assert seen["max_age"] == (0.0 if fresh else 3.0)
