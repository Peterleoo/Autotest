# -*- coding: utf-8 -*-
"""设备列表、投屏、触控与前台应用接口"""
from fastapi import APIRouter
import re
import time
import subprocess
import asyncio
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, Body
from fastapi.responses import JSONResponse, Response, StreamingResponse
from config.settings import settings
from core.screen_stream_hub import screen_stream_hub, STREAM_FRAME_INTERVAL, STREAM_IDLE_FRAME_INTERVAL, STREAM_POLL_SLEEP

from web.shared import (
    app_mgr,
    task_mgr,
    logger,
    resolve_target_device_id,
)

router = APIRouter()


# 投屏期间需要实时画面的会话状态（运行中 / 人机协同等待用户在投屏上操作）
_LIVE_STREAM_STATUSES = {"RUNNING", "WAITING_USER_INPUT", "AWAITING_USER_INPUT"}
MJPEG_KEEPALIVE_SECONDS = 1.0  # MJPEG 画面静止时重发上一帧的间隔


def _stream_interval_for(device_id: str) -> float:
    """设备上有测试运行时实时采集，否则降频：每帧都是真机端满分辨率截屏，空闲高频采集徒增耗电发热"""
    for sess in list(task_mgr.sessions.values()):
        if sess.get("status") not in _LIVE_STREAM_STATUSES:
            continue
        devices = set(sess.get("target_devices") or []) | set((sess.get("devices") or {}).keys())
        if device_id in devices:
            return STREAM_FRAME_INTERVAL
    return STREAM_IDLE_FRAME_INTERVAL


# ================= 优化：设备列表内存级低开销缓存 (5秒 TTL，杜绝高频 ADB 子进程与物理点击探针) =================
_DEVICE_CACHE = {"timestamp": 0.0, "data": None}
DEVICE_LIST_TIMEOUT = 8.0  # 投屏/测试占用 ADB 时 3s 易超时，导致界面误报无设备


@router.get("/api/devices")
async def get_devices(probe: bool = False, force: bool = False):
    """获取所有连接的真机/模拟器设备 (带 5秒轻量缓存与安全探针，杜绝重复进程与 ADB 管道抢占)"""
    global _DEVICE_CACHE
    now = time.time()
    if not force and not probe and _DEVICE_CACHE["data"] is not None and (now - _DEVICE_CACHE["timestamp"] < 5.0):
        return _DEVICE_CACHE["data"]

    devices = []
    adb_bin = app_mgr.adb_bin
    try:
        res = await asyncio.to_thread(lambda: subprocess.run([adb_bin, "devices", "-l"], capture_output=True, text=True, timeout=DEVICE_LIST_TIMEOUT))
    except Exception as e:
        return _device_list_fallback(f"adb devices 执行失败: {e}")
    if res.returncode != 0:
        return _device_list_fallback(f"adb devices 返回码 {res.returncode}: {(res.stderr or '').strip()[:200]}")

    try:
        for line in res.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                dev_id = parts[0]
                model = "Android 真机"
                version = "14.0"
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.replace("model:", "").replace("_", " ")
                    elif p.startswith("device:"):
                        dev_id_alias = p.replace("device:", "")
                
                # 🚀 联动设备画像（避免常规轮询打真实 tap 探针，仅在 probe=True 时探测）
                from core.device_knowledge_manager import device_knowledge_mgr
                dev_fp = device_knowledge_mgr.get_device_fingerprint(dev_id)
                input_healthy = True
                input_tip = ""
                if probe:
                    input_healthy, input_tip = device_knowledge_mgr.probe_input_permission(dev_id)
                
                devices.append({
                    "id": dev_id,
                    "model": f"{dev_fp.get('brand')} {dev_fp.get('model')}" if dev_fp.get("brand") != "Android" else model,
                    "brand": dev_fp.get("brand", "Android"),
                    "raw_model": dev_fp.get("model", model),
                    "rom": dev_fp.get("rom", ""),
                    "platform": "Android",
                    "version": version,
                    "input_healthy": input_healthy,
                    "input_tip": input_tip or "",
                    "status": "在线 (Online)"
                })
    except Exception as e:
        return _device_list_fallback(f"解析设备列表失败: {e}")

    result = {"android_devices": devices, "ios_node": _build_ios_node()}
    _DEVICE_CACHE["timestamp"] = now
    _DEVICE_CACHE["data"] = result
    return result


def _build_ios_node() -> Dict[str, Any]:
    return {
        "id": "remote-ios",
        "model": settings.IOS_DEVICE_NAME,
        "platform": "iOS",
        "version": settings.IOS_PLATFORM_VERSION,
        "status": f"局域网 Mac: {settings.APPIUM_SERVER_URL}"
    }


def _device_list_fallback(reason: str) -> Dict[str, Any]:
    """adb 查询瞬时失败时不写缓存：优先沿用上次成功结果，避免界面误显示"设备掉线\""""
    logger.warning(f"获取设备列表失败，沿用上次结果: {reason}")
    if _DEVICE_CACHE["data"] is not None:
        return _DEVICE_CACHE["data"]
    return {"android_devices": [], "ios_node": _build_ios_node()}


_DEVICE_DIMENSIONS_CACHE: Dict[str, Tuple[int, int]] = {}


def _get_device_screen_dimensions(device_id: str) -> Tuple[int, int]:
    """获取目标真机的真实物理分辨率 (带内存缓存，优先从 Frame 获取，降级使用 wm size)"""
    if device_id in _DEVICE_DIMENSIONS_CACHE:
        return _DEVICE_DIMENSIONS_CACHE[device_id]

    # 1. 尝试从 screen_stream_hub 内存缓存中获取真实帧的宽高
    cached = screen_stream_hub._cache.get(device_id)
    if cached and cached.get("w") and cached.get("h"):
        dim = (int(cached["w"]), int(cached["h"]))
        _DEVICE_DIMENSIONS_CACHE[device_id] = dim
        return dim

    # 2. 降级通过 adb shell wm size 快速探查
    try:
        res = subprocess.run([app_mgr.adb_bin, "-s", device_id, "shell", "wm", "size"], capture_output=True, text=True, timeout=2)
        match = re.findall(r"(\d+)x(\d+)", res.stdout)
        if match:
            w, h = map(int, match[-1])
            _DEVICE_DIMENSIONS_CACHE[device_id] = (w, h)
            return (w, h)
    except Exception:
        logger.debug("忽略异常 @ _get_device_screen_dimensions", exc_info=True)

    return (1080, 2400)


@router.get("/api/devices/{device_id}/screenshot")
@router.get("/api/device/screenshot")
async def get_device_screenshot(device_id: Optional[str] = None, format: str = "jpeg", quality: int = 70, fresh: bool = False):
    """获取指定真机设备的实时屏幕截图 (依托显存 RAW 直读与 PC 端 SIMD 硬件级转码，耗时压缩至 0.6s，内存 0ms 秒回)"""
    target_dev = resolve_target_device_id(device_id)
    if not target_dev:
        return Response(status_code=404, content=b"No device connected", media_type="text/plain")
    # fresh=1：AI 测试子进程感知取帧，跳过帧缓存直接取最新画面（推流下几乎零成本）
    max_age = 0.0 if fresh else _stream_interval_for(target_dev)

    try:
        # 1. 优先通过极速屏幕采集分发中枢获取；帧在 STREAM_FRAME_INTERVAL 内复用，任何前端轮询都无法把 ADB 通道打满
        if format.lower() == "png":
            png_bytes = await screen_stream_hub.get_png_bytes(target_dev, max_age=max_age)
            if png_bytes:
                return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        else:
            jpeg_bytes = await screen_stream_hub.get_jpeg_bytes(target_dev, max_age=max_age)
            if jpeg_bytes:
                return Response(content=jpeg_bytes, media_type="image/jpeg", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    except Exception as e:
        logger.warning(f"获取设备 [{target_dev}] 极速屏幕截图异常: {e}")

    # 🌟 杜绝伪造历史截屏：当物理真机断开时坚决返回 404，由前端平滑呈现未连接排查指引
    return Response(status_code=404, content=b"Device screenshot unavailable", media_type="text/plain")


# =========================================================================
# 🌟 原生 ADB 极速 MJPEG 帧流发生器与鼠标穿透控制 (KISS 原则 · 零外部重型依赖)
# =========================================================================

@router.get("/api/device/screen/stream")
@router.get("/api/devices/{device_id}/screen/stream")
async def stream_device_screen(request: Request, device_id: Optional[str] = None):
    """原生 ADB 极速 MJPEG 实时帧流发生器 (依托显存 RAW 直读 + OpenCV SIMD，端到端延迟低至 600ms)"""
    import asyncio

    target_dev = resolve_target_device_id(device_id)
    if not target_dev:
        return Response(status_code=404, content=b"No online device connected", media_type="text/plain")

    async def frame_generator():
        last_sent, last_sent_at = None, 0.0
        while True:
            if await request.is_disconnected():
                break
            try:
                # 限流：同一帧在 STREAM_FRAME_INTERVAL 内复用，给测试 ADB 指令留出通道空闲窗口
                jpeg_bytes = await screen_stream_hub.get_jpeg_bytes(target_dev, max_age=_stream_interval_for(target_dev))
                # 画面静止时（scrcpy 推流不出新帧）按保活间隔重发上一帧，维持流活性，不增加真机负载
                is_new = jpeg_bytes is not last_sent
                if jpeg_bytes and (is_new or time.time() - last_sent_at >= MJPEG_KEEPALIVE_SECONDS):
                    last_sent, last_sent_at = jpeg_bytes, time.time()
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n")
                await asyncio.sleep(STREAM_POLL_SLEEP)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


@router.post("/api/device/tap")
async def tap_device(payload: Dict[str, Any] = Body(...)):
    """鼠标穿透控制：接收网页点击相对坐标或归一化比例，转化为真机 ADB 物理手势"""
    dev_id = resolve_target_device_id(payload.get("device_id"))
    if not dev_id:
        return JSONResponse({"success": False, "error": "No online device available"})

    norm_x = payload.get("norm_x")
    norm_y = payload.get("norm_y")
    if norm_x is not None and norm_y is not None:
        dim = _get_device_screen_dimensions(dev_id)
        x = int(float(norm_x) * dim[0])
        y = int(float(norm_y) * dim[1])
    else:
        x = int(payload.get("x", 0))
        y = int(payload.get("y", 0))
    if x <= 0 or y <= 0:
        return JSONResponse({"success": False, "error": "Invalid coordinates"})

    adb_bin = app_mgr.adb_bin
    try:
        res = await asyncio.to_thread(lambda: subprocess.run([adb_bin, "-s", dev_id, "shell", "input", "tap", str(x), str(y)], capture_output=True, timeout=2))
        screen_stream_hub.invalidate_cache(dev_id)
        return JSONResponse({"success": True, "x": x, "y": y, "returncode": res.returncode})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/api/device/swipe")
async def swipe_device(payload: Dict[str, Any] = Body(...)):
    """真机拖拽/滑动穿透控制：接收滑动起点与终点物理坐标或归一化比例及持续时间"""
    dev_id = resolve_target_device_id(payload.get("device_id"))
    if not dev_id:
        return JSONResponse({"success": False, "error": "No online device available"})

    norm_x1 = payload.get("norm_x1")
    norm_y1 = payload.get("norm_y1")
    norm_x2 = payload.get("norm_x2")
    norm_y2 = payload.get("norm_y2")
    if None not in (norm_x1, norm_y1, norm_x2, norm_y2):
        dim = _get_device_screen_dimensions(dev_id)
        x1 = int(float(norm_x1) * dim[0])
        y1 = int(float(norm_y1) * dim[1])
        x2 = int(float(norm_x2) * dim[0])
        y2 = int(float(norm_y2) * dim[1])
    else:
        x1 = int(payload.get("x1", 0))
        y1 = int(payload.get("y1", 0))
        x2 = int(payload.get("x2", 0))
        y2 = int(payload.get("y2", 0))

    duration = int(payload.get("duration", 300))
    if x1 <= 0 or y1 <= 0 or x2 <= 0 or y2 <= 0:
        return JSONResponse({"success": False, "error": "Invalid coordinates"})

    adb_bin = app_mgr.adb_bin
    try:
        res = await asyncio.to_thread(lambda: subprocess.run(
            [adb_bin, "-s", dev_id, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)],
            capture_output=True, timeout=3
        ))
        screen_stream_hub.invalidate_cache(dev_id)
        return JSONResponse({"success": True, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration, "returncode": res.returncode})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/api/device/key")
async def send_device_key(payload: Dict[str, Any] = Body(...)):
    """真机按键控制：支持返回、桌面、多任务等虚拟导航键"""
    dev_id = resolve_target_device_id(payload.get("device_id"))
    if not dev_id:
        return JSONResponse({"success": False, "error": "No online device available"})
    key = str(payload.get("key", "")).lower()
    key_map = {"back": "4", "home": "3", "app_switch": "187", "menu": "82", "volume_up": "24", "volume_down": "25"}
    keycode = key_map.get(key, key)
    if not keycode:
        return JSONResponse({"success": False, "error": "Invalid key"})

    adb_bin = app_mgr.adb_bin
    try:
        res = await asyncio.to_thread(lambda: subprocess.run(
            [adb_bin, "-s", dev_id, "shell", "input", "keyevent", keycode],
            capture_output=True, timeout=2
        ))
        screen_stream_hub.invalidate_cache(dev_id)
        return JSONResponse({"success": True, "key": key, "keycode": keycode, "returncode": res.returncode})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.get("/api/device/installed_apps")
async def get_device_installed_apps(device_id: Optional[str] = None, include_system: bool = False):
    """🚀 0.08s 极速读取已连接真机上已安装的桌面应用列表 (无需上传 APK)"""
    dev = device_id
    if not dev:
        connected = app_mgr.get_connected_devices()
        dev = connected[0] if connected else None
    if not dev:
        return {"success": False, "apps": [], "message": "未连接任何物理真机设备"}
    apps = app_mgr.get_device_installed_apps(device_id=dev, include_system=include_system)
    return {"success": True, "device_id": dev, "apps": apps, "total": len(apps)}


@router.get("/api/device/foreground_app")
async def get_device_foreground_app(device_id: Optional[str] = None):
    """0.05s 极速捕获真机当前屏幕前台正在运行的应用包名、Activity 与识别名称"""
    dev = device_id
    if not dev:
        connected = app_mgr.get_connected_devices()
        dev = connected[0] if connected else None
    if not dev:
        return {"success": False, "app": None, "message": "未连接任何物理真机设备"}
    fg = app_mgr.get_current_foreground_app(device_id=dev)
    return {"success": True, "device_id": dev, "app": fg}


@router.post("/api/device/app_label")
async def save_device_app_label(payload: Dict[str, str] = Body(...)):
    """保存用户自定义的应用中文名称 (持久化记忆)"""
    pkg = payload.get("package", "").strip()
    lbl = payload.get("label", "").strip()
    if not pkg or not lbl:
        return JSONResponse(status_code=400, content={"success": False, "message": "包名和名称不能为空"})
    app_mgr.save_custom_app_label(pkg, lbl)
    return {"success": True, "package": pkg, "label": lbl}
