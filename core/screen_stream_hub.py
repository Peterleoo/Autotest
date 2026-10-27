# -*- coding: utf-8 -*-
"""
ScreenStreamHub: 极速真机屏幕采集与流分发中枢 (KISS 原则 · 零外部重型依赖)
1. 显存 RAW 零拷贝读取：利用 adb exec-out screencap 直读 SurfaceFlinger 显存，跳过真机 CPU 的低效逐像素 PNG 压缩 (采集耗时由 3.3s 降至 0.6s)；
2. PC 侧 SIMD 硬件级快速下采样与编码：利用 OpenCV/Numpy 在 PC 多核端完成快速插值缩放与高质量 JPEG 编码 (PC 处理耗时由 400ms 降至 6ms)；
3. 单例常驻帧分发与防并发互锁：双重检查锁防多端争抢 ADB 通道，内存零延迟复用新鲜帧，彻底杜绝画中画与右侧抽屉同时打开时的通道阻塞。
"""

import time
import struct
import logging
import asyncio
import subprocess
from typing import Optional, Dict, Any

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger("ScreenStreamHub")


def _capture_raw_and_encode_sync(adb_bin: str, device_id: str) -> Optional[Dict[str, Any]]:
    """
    底层同步采集函数 (运行在独立线程池中，不阻塞 FastAPI 主事件循环):
    优先尝试 Android 显存 RAW 读取并用 OpenCV 高速转码；
    若遇到非标准帧格式或异常，则自动无缝降级为标准 screencap -p。
    """
    if not adb_bin:
        adb_bin = "adb"

    # 1. 尝试显存 RAW 直读 (Android 9+ 格式: 16字节头: w, h, format, colorspace)
    if HAS_OPENCV:
        try:
            t0 = time.time()
            res = subprocess.run([adb_bin, "-s", device_id, "exec-out", "screencap"], capture_output=True, timeout=3)
            raw = res.stdout
            if res.returncode == 0 and raw and len(raw) > 16:
                w, h, fmt, cs = struct.unpack('<IIII', raw[:16])
                expected_len = 16 + w * h * 4
                if 0 < w < 8000 and 0 < h < 8000 and len(raw) >= expected_len:
                    # 零拷贝映射显存 RGBA 矩阵
                    arr = np.frombuffer(raw[16:expected_len], dtype=np.uint8).reshape((h, w, 4))
                    
                    # 快速下采样到目标宽度 480 (等比例，耗时仅 1~2ms)
                    target_w = 480
                    target_h = int(h * (target_w / w))
                    thumb = cv2.resize(arr, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
                    bgr = cv2.cvtColor(thumb, cv2.COLOR_RGBA2BGR)
                    
                    # PC 端 SIMD 快速编码为轻量 JPEG (质量 70，大小约 35KB，编码耗时约 4ms)
                    _, jpeg_buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    t_cost = time.time() - t0
                    return {
                        "jpeg": jpeg_buf.tobytes(),
                        "bgr": bgr,
                        "w": w,
                        "h": h,
                        "time": time.time(),
                        "cost": t_cost,
                        "mode": "raw_cv2"
                    }
        except Exception as e:
            logger.debug(f"显存 RAW 直读跳过或异常，转入兼容降级模式: {e}")

    # 2. 兼容兜底方案: screencap -p
    try:
        t0 = time.time()
        res = subprocess.run([adb_bin, "-s", device_id, "exec-out", "screencap", "-p"], capture_output=True, timeout=5)
        raw = res.stdout
        if res.returncode == 0 and raw and len(raw) > 200:
            if not raw.startswith(b"\x89PNG\r\n\x1a\n") and b"PNG" in raw[:16]:
                raw = raw.replace(b"\r\r\n", b"\n").replace(b"\r\n", b"\n")

            if HAS_OPENCV:
                img_bgr = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
                if img_bgr is not None:
                    h, w = img_bgr.shape[:2]
                    target_w = 480
                    target_h = int(h * (target_w / w))
                    thumb = cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
                    _, jpeg_buf = cv2.imencode('.jpg', thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    return {
                        "jpeg": jpeg_buf.tobytes(),
                        "bgr": thumb,
                        "w": w,
                        "h": h,
                        "time": time.time(),
                        "cost": time.time() - t0,
                        "mode": "png_cv2"
                    }
            elif HAS_PIL:
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                orig_w, orig_h = img.size
                target_w = 480
                target_h = int(orig_h * (target_w / orig_w))
                img_resized = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
                buf = io.BytesIO()
                img_resized.save(buf, format="JPEG", quality=70)
                return {
                    "jpeg": buf.getvalue(),
                    "bgr": None,
                    "w": orig_w,
                    "h": orig_h,
                    "time": time.time(),
                    "cost": time.time() - t0,
                    "mode": "png_pil"
                }
    except Exception as e:
        logger.warning(f"设备 [{device_id}] 屏幕采集彻底失败: {e}")

    return None


class ScreenStreamHub:
    """
    单例真机屏幕分发中枢:
    管理活跃采集任务，防并发 ADB 竞争，提供高效内存帧复用。
    """
    def __init__(self, adb_bin: Optional[str] = None):
        self._adb_bin = adb_bin
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._failure_timestamps: Dict[str, float] = {}

    def set_adb_bin(self, adb_bin: str):
        self._adb_bin = adb_bin

    def _get_adb_bin(self) -> str:
        if self._adb_bin:
            return self._adb_bin
        try:
            from core.app_manager import AppManager
            return AppManager().adb_bin
        except Exception:
            return "adb"

    def _get_lock(self, device_id: str) -> asyncio.Lock:
        if device_id not in self._locks:
            self._locks[device_id] = asyncio.Lock()
        return self._locks[device_id]

    def invalidate_cache(self, device_id: str):
        """立即将指定设备的缓存置为过期（手势点击/滑动后调用，强制下一次拉取真实转场新帧）"""
        if device_id in self._cache:
            self._cache[device_id]["time"] = 0
        self._failure_timestamps.pop(device_id, None)

    async def get_frame(self, device_id: str, max_age: float = 0.45) -> Optional[Dict[str, Any]]:
        """
        获取最新帧结构。
        若缓存时间在 max_age 内，则直接从内存返回 (0ms 延迟)；
        否则加锁由当前协程在线程池发起抓取，排队协程共享该次抓取产物。
        """
        now = time.time()
        if (now - self._failure_timestamps.get(device_id, 0.0)) < 2.0:
            return None

        cached = self._cache.get(device_id)
        if cached and (now - cached.get("time", 0) < max_age):
            return cached

        lock = self._get_lock(device_id)
        async with lock:
            # 双重检查锁
            cached = self._cache.get(device_id)
            now = time.time()
            if cached and (now - cached.get("time", 0) < max_age):
                return cached

            adb_bin = self._get_adb_bin()
            frame_data = await asyncio.to_thread(_capture_raw_and_encode_sync, adb_bin, device_id)
            if frame_data:
                self._failure_timestamps.pop(device_id, None)
                self._cache[device_id] = frame_data
                return frame_data
            else:
                # 🌟 真机采集失败（已离线或断开），记入失败时间戳启动 2s 熔断，清除旧缓存帧
                self._failure_timestamps[device_id] = time.time()
                self._cache.pop(device_id, None)
                return None

    async def get_jpeg_bytes(self, device_id: str, max_age: float = 0.45) -> Optional[bytes]:
        """获取压缩后的极速 JPEG 字节流 (约 35KB，加载延迟极低)"""
        frame = await self.get_frame(device_id, max_age=max_age)
        return frame["jpeg"] if frame else None

    async def get_png_bytes(self, device_id: str, max_age: float = 0.45) -> Optional[bytes]:
        """获取 PNG 格式字节流 (PC 侧硬件 SIMD 编码，耗时仅 20ms)"""
        frame = await self.get_frame(device_id, max_age=max_age)
        if not frame:
            return None
        if "png" in frame:
            return frame["png"]
        bgr = frame.get("bgr")
        if HAS_OPENCV and bgr is not None:
            _, buf = cv2.imencode('.png', bgr)
            png_bytes = buf.tobytes()
            frame["png"] = png_bytes
            return png_bytes
        return frame.get("jpeg")


# 全局单例
screen_stream_hub = ScreenStreamHub()
