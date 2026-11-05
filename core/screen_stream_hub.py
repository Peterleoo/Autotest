# -*- coding: utf-8 -*-
"""
ScreenStreamHub: 极速真机屏幕采集与流分发中枢 (KISS 原则 · 零外部重型依赖)
1. 显存 RAW 直读 + 端侧 gzip -1 压缩传输：跳过真机 CPU 的低效 PNG 压缩 (3.3s -> 0.5s)，USB 传输量 9.3MB -> 2.4MB，减轻老旧真机 USB 链路压力；
2. PC 侧 SIMD 硬件级快速下采样与编码：利用 OpenCV/Numpy 在 PC 多核端完成快速插值缩放与高质量 JPEG 编码 (PC 处理耗时由 400ms 降至 6ms)；
3. 单例常驻帧分发与防并发互锁：双重检查锁防多端争抢 ADB 通道，内存零延迟复用新鲜帧，彻底杜绝画中画与右侧抽屉同时打开时的通道阻塞。
"""

import os
import gzip
import time
import struct
import logging
import asyncio
import subprocess
from typing import Optional, Dict, Any, List, Tuple

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

RAW_CAPTURE_TIMEOUT = 6.0       # RAW 帧约 10MB，3s 在 USB 繁忙时极易超时并中途杀进程，诱发 offline 抖动
PNG_CAPTURE_TIMEOUT = 8.0
STREAM_FRAME_INTERVAL = 0.8     # MJPEG 帧流最小采集间隔：给测试指令留出 ADB 通道空闲窗口，杜绝通道被投屏占满
STREAM_IDLE_FRAME_INTERVAL = 3.0  # 设备无测试运行时的采集间隔：每帧都是真机端满分辨率截屏，空闲降频以省电降温
STREAM_POLL_SLEEP = 0.1
# 端侧 gzip 压缩截屏：减少 USB 传输量，但压缩消耗真机 CPU；老机型可设 DEVICE_GZIP_CAPTURE=0 关闭以省电
DEVICE_GZIP_CAPTURE = os.getenv("DEVICE_GZIP_CAPTURE", "1").strip().lower() not in ("0", "false", "no", "off")
FAILURE_THRESHOLD = 3           # 连续失败 N 次才判定断连，单次抖动继续展示上一帧
FAILURE_COOLDOWN = 2.0          # 判定断连后的熔断冷却时间


GZIP_MAGIC = bytes([0x1F, 0x8B])  # gzip 流魔数
_GZIP_UNSUPPORTED: set = set()  # 端侧无 gzip 的设备，后续直接走原始 RAW，避免每帧白跑一次


def _raw_capture_variants(device_id: str) -> List[Tuple[str, str]]:
    use_gzip = DEVICE_GZIP_CAPTURE and device_id not in _GZIP_UNSUPPORTED
    variants = [("raw_gzip_cv2", "screencap | gzip -1")] if use_gzip else []
    return variants + [("raw_cv2", "screencap")]


def _unpack_capture_payload(device_id: str, mode: str, payload: bytes) -> Optional[bytes]:
    """gzip 模式下解压；输出不是 gzip 流说明端侧不支持 gzip，记录后降级。传输截断等瞬时错误不做永久降级"""
    if mode != "raw_gzip_cv2":
        return payload
    if not payload.startswith(GZIP_MAGIC):
        _GZIP_UNSUPPORTED.add(device_id)
        logger.info(f"设备 [{device_id}] 端侧不支持 gzip 压缩截屏，回退原始 RAW 传输")
        return None
    return gzip.decompress(payload)


def _decode_raw_frame(raw: bytes) -> Optional[Dict[str, Any]]:
    """解析 Android 9+ screencap RAW (16 字节头: w, h, format, colorspace) 并在 PC 端缩放编码为 JPEG"""
    if len(raw) <= 16:
        return None
    w, h, _fmt, _cs = struct.unpack('<IIII', raw[:16])
    expected_len = 16 + w * h * 4
    if not (0 < w < 8000 and 0 < h < 8000 and len(raw) >= expected_len):
        return None
    arr = np.frombuffer(raw[16:expected_len], dtype=np.uint8).reshape((h, w, 4))
    target_w = 480
    target_h = int(h * (target_w / w))
    thumb = cv2.resize(arr, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
    bgr = cv2.cvtColor(thumb, cv2.COLOR_RGBA2BGR)
    _, jpeg_buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    return {"jpeg": jpeg_buf.tobytes(), "bgr": bgr, "w": w, "h": h}


def _capture_raw_and_encode_sync(adb_bin: str, device_id: str) -> Optional[Dict[str, Any]]:
    """
    底层同步采集函数 (运行在独立线程池中，不阻塞 FastAPI 主事件循环):
    优先尝试 Android 显存 RAW 读取并用 OpenCV 高速转码；
    若遇到非标准帧格式或异常，则自动无缝降级为标准 screencap -p。
    """
    if not adb_bin:
        adb_bin = "adb"

    # 1. 显存 RAW 直读：优先端侧 gzip 压缩传输 (9.3MB -> 2.4MB，耗时不变)，不支持 gzip 的设备回退原始 RAW
    if HAS_OPENCV:
        for mode, cmd in _raw_capture_variants(device_id):
            try:
                t0 = time.time()
                res = subprocess.run([adb_bin, "-s", device_id, "exec-out", cmd], capture_output=True, timeout=RAW_CAPTURE_TIMEOUT)
                if res.returncode != 0 or not res.stdout:
                    continue
                raw = _unpack_capture_payload(device_id, mode, res.stdout)
                frame = _decode_raw_frame(raw) if raw else None
                if frame:
                    return {**frame, "time": time.time(), "cost": time.time() - t0, "mode": mode}
            except Exception as e:
                logger.debug(f"显存 RAW 直读 [{mode}] 跳过或异常，尝试下一种方式: {e}")

    # 2. 兼容兜底方案: screencap -p
    try:
        t0 = time.time()
        res = subprocess.run([adb_bin, "-s", device_id, "exec-out", "screencap", "-p"], capture_output=True, timeout=PNG_CAPTURE_TIMEOUT)
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
        self._failure_counts: Dict[str, int] = {}

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
        self._failure_counts.pop(device_id, None)

    async def get_frame(self, device_id: str, max_age: float = 0.45) -> Optional[Dict[str, Any]]:
        """
        获取最新帧结构。
        若缓存时间在 max_age 内，则直接从内存返回 (0ms 延迟)；
        否则加锁由当前协程在线程池发起抓取，排队协程共享该次抓取产物。
        """
        now = time.time()
        if (now - self._failure_timestamps.get(device_id, 0.0)) < FAILURE_COOLDOWN:
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
                self._failure_counts.pop(device_id, None)
                self._cache[device_id] = frame_data
                return frame_data
            return self._handle_capture_failure(device_id)

    def _handle_capture_failure(self, device_id: str) -> Optional[Dict[str, Any]]:
        """单次采集抖动沿用上一帧；连续失败达到阈值才判定断连、熔断并清除缓存帧"""
        count = self._failure_counts.get(device_id, 0) + 1
        self._failure_counts[device_id] = count
        if count < FAILURE_THRESHOLD:
            logger.debug(f"设备 [{device_id}] 屏幕采集失败 {count}/{FAILURE_THRESHOLD}，沿用上一帧")
            return self._cache.get(device_id)
        logger.warning(f"设备 [{device_id}] 屏幕连续采集失败 {count} 次，判定断连并熔断 {FAILURE_COOLDOWN}s")
        self._failure_counts.pop(device_id, None)
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
