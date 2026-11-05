# -*- coding: utf-8 -*-
"""
scrcpy 硬件 H.264 推流：替代反复全分辨率 screencap 的投屏帧来源

真机端用硬件编码器推送 H.264（画面静止时几乎不出帧），PC 端用 PyAV 解码，按需输出与
screen_stream_hub 截屏帧完全一致的帧结构（480 宽缩略图 bgr/jpeg + 真机原始宽高 w/h）。
实测 Mi MIX 2：10fps 推流额外耗电约为 screencap 每 0.8s 一帧的 1/3，USB 传输量约 1/30。

- 按需启动：首次取帧时启动，空闲 STREAM_IDLE_STOP_SECONDS 无人取帧自动停止
- 两档帧率：有测试运行(live)用 LIVE_FPS，否则 IDLE_FPS；档位变化时重启推流
- 失败降级：启动/推流失败后该设备 FAILURE_COOLDOWN 秒内返回 None，由调用方回退 screencap
"""
import atexit
import logging
import os
import re
import secrets
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("ScrcpyStream")

SCRCPY_VERSION = "5.0.1"
SERVER_LOCAL = Path(os.getenv("SCRCPY_SERVER_PATH") or
                    Path(__file__).resolve().parent.parent / "tools" / "scrcpy" / f"scrcpy-server-v{SCRCPY_VERSION}")
SERVER_REMOTE = "/data/local/tmp/autotest-scrcpy-server.jar"
BACKEND = os.getenv("SCREEN_STREAM_BACKEND", "auto").strip().lower()  # auto | scrcpy | screencap

MAX_SIZE = int(os.getenv("SCRCPY_MAX_SIZE", "960"))
LIVE_FPS = int(os.getenv("SCRCPY_LIVE_FPS", "10"))
IDLE_FPS = int(os.getenv("SCRCPY_IDLE_FPS", "2"))
VIDEO_BIT_RATE = int(os.getenv("SCRCPY_BIT_RATE", "2000000"))
THUMB_WIDTH = 480
FIRST_FRAME_TIMEOUT = 4.0
STREAM_IDLE_STOP_SECONDS = 30.0
FAILURE_COOLDOWN = 300.0


def _decoder_available() -> bool:
    try:
        import av  # noqa: F401
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


class ScrcpyStream:
    """单设备的一路 scrcpy 推流 + 解码线程"""

    def __init__(self, adb_bin: str, device_id: str, max_fps: int):
        self.adb_bin, self.device_id, self.max_fps = adb_bin, device_id, max_fps
        self.scid = f"{secrets.randbits(31):08x}"
        self.port: Optional[int] = None
        self.proc: Optional[subprocess.Popen] = None
        self.sock: Optional[socket.socket] = None
        self.native_size: Optional[Tuple[int, int]] = None
        self._lock = threading.Lock()
        self._latest = None          # 最新解码帧 (bgr ndarray)
        self._latest_seq = 0
        self._encoded: Optional[Dict[str, Any]] = None
        self._encoded_seq = -1
        self._first_frame = threading.Event()
        self._stopped = threading.Event()
        self.error: Optional[str] = None

    # ---------------- 生命周期 ----------------
    def _adb(self, *args, timeout=15) -> subprocess.CompletedProcess:
        return subprocess.run([self.adb_bin, "-s", self.device_id, *args], capture_output=True, text=True, timeout=timeout)

    def _ensure_server_pushed(self):
        size = self._adb("shell", f"stat -c %s {SERVER_REMOTE} 2>/dev/null").stdout.strip()
        if size != str(SERVER_LOCAL.stat().st_size):
            res = self._adb("push", str(SERVER_LOCAL), SERVER_REMOTE, timeout=30)
            if res.returncode != 0:
                raise RuntimeError(f"推送 scrcpy-server 失败: {res.stderr.strip()}")

    def _read_native_size(self):
        out = self._adb("shell", "wm size").stdout
        override = re.search(r"Override size:\s*(\d+)x(\d+)", out)
        physical = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
        m = override or physical
        if m:
            self.native_size = (int(m.group(1)), int(m.group(2)))

    def start(self):
        self._ensure_server_pushed()
        self._read_native_size()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        res = self._adb("forward", f"tcp:{self.port}", f"localabstract:scrcpy_{self.scid}")
        if res.returncode != 0:
            raise RuntimeError(f"adb forward 失败: {res.stderr.strip()}")
        args = [f"scid={self.scid}", "tunnel_forward=true", "audio=false", "control=false", "cleanup=true",
                "raw_stream=true", f"max_size={MAX_SIZE}", f"max_fps={self.max_fps}",
                f"video_bit_rate={VIDEO_BIT_RATE}", "log_level=warn"]
        self.proc = subprocess.Popen(
            [self.adb_bin, "-s", self.device_id, "shell", f"CLASSPATH={SERVER_REMOTE}", "app_process", "/",
             "com.genymobile.scrcpy.Server", SCRCPY_VERSION, *args],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        threading.Thread(target=self._pump_server_log, daemon=True).start()
        first_chunk = self._connect()
        threading.Thread(target=self._decode_loop, args=(first_chunk,), daemon=True).start()
        logger.info(f"📺 scrcpy 推流已启动: {self.device_id} max_size={MAX_SIZE} fps={self.max_fps}")

    def _connect(self) -> bytes:
        deadline = time.time() + 10
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("scrcpy-server 进程提前退出")
            try:
                sock = socket.create_connection(("127.0.0.1", self.port), timeout=3)
                sock.settimeout(5)
                chunk = sock.recv(65536)  # 服务端未就绪时连接会被立即关闭(读到空)
                if chunk:
                    self.sock = sock
                    return chunk
                sock.close()
            except OSError:
                pass
            time.sleep(0.25)
        raise RuntimeError("连接 scrcpy 视频流超时")

    def _pump_server_log(self):
        for line in self.proc.stdout:
            text = line.decode("utf-8", "replace").rstrip()
            if text:
                logger.info(f"[scrcpy-server {self.device_id}] {text}")

    def _decode_loop(self, chunk: bytes):
        import av
        codec = av.CodecContext.create("h264", "r")
        try:
            while not self._stopped.is_set():
                if chunk:
                    for packet in codec.parse(chunk):
                        for frame in codec.decode(packet):
                            bgr = frame.to_ndarray(format="bgr24")
                            with self._lock:
                                self._latest = bgr
                                self._latest_seq += 1
                            self._first_frame.set()
                try:
                    chunk = self.sock.recv(65536)
                    if not chunk:
                        raise ConnectionError("视频流已关闭")
                except socket.timeout:
                    chunk = b""  # 画面静止时编码器不出帧，属正常
        except Exception as e:
            if not self._stopped.is_set():
                self.error = str(e)
                logger.warning(f"scrcpy 推流中断 {self.device_id}: {e}")
        finally:
            self._stopped.set()

    def stop(self):
        self._stopped.set()
        for closer in (lambda: self.sock and self.sock.close(),
                       lambda: self.proc and self.proc.poll() is None and self.proc.kill(),
                       lambda: self.port and self._adb("forward", "--remove", f"tcp:{self.port}", timeout=5)):
            try:
                closer()
            except Exception:
                logger.debug("忽略异常 @ ScrcpyStream.stop", exc_info=True)

    @property
    def alive(self) -> bool:
        return not self._stopped.is_set() and self.proc is not None and self.proc.poll() is None

    # ---------------- 取帧 ----------------
    def latest_frame(self, wait: float = 0.0) -> Optional[Dict[str, Any]]:
        if wait and not self._first_frame.wait(wait):
            return None
        with self._lock:
            bgr, seq = self._latest, self._latest_seq
        if bgr is None:
            return None
        if seq != self._encoded_seq:
            self._encoded = self._encode(bgr)
            self._encoded_seq = seq
        return {**self._encoded, "time": time.time()}

    def _encode(self, bgr) -> Dict[str, Any]:
        import cv2
        h, w = bgr.shape[:2]
        thumb_h = int(h * (THUMB_WIDTH / w))
        thumb = cv2.resize(bgr, (THUMB_WIDTH, thumb_h), interpolation=cv2.INTER_AREA)
        _, jpeg = cv2.imencode(".jpg", thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        native_w, native_h = w, h
        if self.native_size:
            short, long_ = sorted(self.native_size)
            native_w, native_h = (short, long_) if w <= h else (long_, short)
        return {"jpeg": jpeg.tobytes(), "bgr": thumb, "w": native_w, "h": native_h, "cost": 0.0, "mode": "scrcpy_h264"}


class ScrcpyStreamManager:
    """按设备管理推流：按需启动、帧率档位切换、空闲回收、失败冷却"""

    def __init__(self):
        self._streams: Dict[str, ScrcpyStream] = {}
        self._last_access: Dict[str, float] = {}
        self._failed_until: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._reaper_started = False

    @property
    def enabled(self) -> bool:
        if BACKEND == "screencap":
            return False
        return SERVER_LOCAL.exists() and _decoder_available()

    def get_frame(self, adb_bin: str, device_id: str, live: bool) -> Optional[Dict[str, Any]]:
        if not self.enabled or time.time() < self._failed_until.get(device_id, 0):
            return None
        fps = LIVE_FPS if live else IDLE_FPS
        with self._lock:
            self._last_access[device_id] = time.time()
            self._start_reaper()
            stream = self._streams.get(device_id)
            if stream and (not stream.alive or stream.max_fps != fps):
                stream.stop()
                stream = None
            if stream is None:
                stream = ScrcpyStream(adb_bin, device_id, fps)
                try:
                    stream.start()
                except Exception as e:
                    stream.stop()
                    self._failed_until[device_id] = time.time() + FAILURE_COOLDOWN
                    logger.warning(f"scrcpy 推流不可用，{FAILURE_COOLDOWN:.0f}s 内回退 screencap ({device_id}): {e}")
                    return None
                self._streams[device_id] = stream
        frame = stream.latest_frame(wait=FIRST_FRAME_TIMEOUT)
        if frame is None and not stream.alive:
            self._failed_until[device_id] = time.time() + FAILURE_COOLDOWN
        return frame

    def stop(self, device_id: str):
        with self._lock:
            stream = self._streams.pop(device_id, None)
        if stream:
            stream.stop()

    def stop_all(self):
        for device_id in list(self._streams):
            self.stop(device_id)

    def _start_reaper(self):
        if not self._reaper_started:
            self._reaper_started = True
            threading.Thread(target=self._reap_idle, daemon=True).start()

    def _reap_idle(self):
        while True:
            time.sleep(5)
            self._reap_once()

    def _reap_once(self):
        now = time.time()
        for device_id, last in list(self._last_access.items()):
            if now - last > STREAM_IDLE_STOP_SECONDS and device_id in self._streams:
                logger.info(f"📺 scrcpy 推流空闲 {STREAM_IDLE_STOP_SECONDS:.0f}s 无人取帧，已停止: {device_id}")
                self.stop(device_id)


scrcpy_manager = ScrcpyStreamManager()
atexit.register(scrcpy_manager.stop_all)  # 服务退出/热重载时关闭推流，避免真机端继续编码耗电
