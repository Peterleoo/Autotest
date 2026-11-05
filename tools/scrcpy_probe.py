# -*- coding: utf-8 -*-
"""
scrcpy 硬件 H.264 推流 vs 现有 screencap 截屏：真机端负载对比原型（一次性测量工具）

用法：python tools/scrcpy_probe.py [--device SERIAL] [--seconds 60]
阶段：0 基线(亮屏不采集) / 1 screencap 每 0.8s / 2 screencap 每 3s / 3 scrcpy 720p@10fps + PyAV 解码
指标：真机 CPU 占用(/proc/stat)、电池电流均值(current_now)、电池温度、帧数、USB 传输量、PC 端每帧耗时
"""
import argparse
import socket
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.app_manager import AppManager  # noqa: E402
from core.screen_stream_hub import _capture_raw_and_encode_sync  # noqa: E402

SCRCPY_VERSION = "5.0.1"
SERVER_LOCAL = ROOT / "tools" / "scrcpy" / f"scrcpy-server-v{SCRCPY_VERSION}"
SERVER_REMOTE = "/data/local/tmp/scrcpy-server-probe.jar"
FORWARD_PORT = 27199
SOCKET_NAME = "scrcpy"  # scid 未指定时 server 默认使用的 localabstract 名


class Adb:
    def __init__(self, adb_bin: str, serial: str):
        self.adb_bin, self.serial = adb_bin, serial

    def run(self, *args, timeout=15, binary=False):
        res = subprocess.run([self.adb_bin, "-s", self.serial, *args], capture_output=True, timeout=timeout)
        return res.stdout if binary else res.stdout.decode("utf-8", "replace")

    def shell(self, cmd: str, timeout=15) -> str:
        return self.run("shell", cmd, timeout=timeout)


def read_cpu_jiffies(adb: Adb):
    first = adb.shell("head -1 /proc/stat").split()
    vals = [int(x) for x in first[1:8]]
    idle = vals[3] + vals[4]
    return sum(vals), idle


def read_battery(adb: Adb):
    """sysfs 电流节点在多数 ROM 上 shell 无权读取；改用 dumpsys battery 的 Charge counter(µAh) 与温度"""
    counter = temp = level = None
    for line in adb.shell("dumpsys battery").splitlines():
        key, _, val = line.strip().partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "charge counter" and val.lstrip("-").isdigit():
            counter = int(val)
        elif key == "temperature" and val.lstrip("-").isdigit():
            temp = int(val) / 10.0
        elif key == "level" and val.isdigit():
            level = int(val)
    return counter, temp, level


class Sampler:
    """阶段起止读取 Charge counter 计算平均净电流（正=充电、负=放电），期间每 5s 记录温度；CPU 按 /proc/stat 差值"""

    def __init__(self, adb: Adb):
        self.adb, self.temps, self.stop = adb, [], threading.Event()

    def __enter__(self):
        self.cpu0 = read_cpu_jiffies(self.adb)
        self.t0 = time.time()
        self.counter0, temp, _ = read_battery(self.adb)
        self.temps.append(temp)
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def _loop(self):
        while not self.stop.wait(5.0):
            _, temp, _ = read_battery(self.adb)
            self.temps.append(temp)

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=10)
        total1, idle1 = read_cpu_jiffies(self.adb)
        total0, idle0 = self.cpu0
        busy = (total1 - total0) - (idle1 - idle0)
        self.cpu_pct = 100.0 * busy / max(1, total1 - total0)
        self.counter1, temp, self.level = read_battery(self.adb)
        self.temps.append(temp)
        self.elapsed = time.time() - self.t0

    def summary(self):
        net_ma = float("nan")
        if self.counter0 is not None and self.counter1 is not None and self.elapsed > 0:
            net_ma = (self.counter1 - self.counter0) / (self.elapsed / 3600.0) / 1000.0
        temps = [t for t in self.temps if t is not None]
        return {"cpu_pct": round(self.cpu_pct, 1), "net_current_mA": round(net_ma, 1),
                "temp_C": f"{temps[0]}->{temps[-1]}" if temps else None, "level": self.level}


def phase_baseline(adb: Adb, seconds: float):
    with Sampler(adb) as s:
        time.sleep(seconds)
    return {**s.summary(), "frames": 0, "usb_MB_est": 0.0, "pc_ms_per_frame": 0.0}


def phase_screencap(adb: Adb, seconds: float, interval: float):
    frames, pc_ms = 0, []
    with Sampler(adb) as s:
        end = time.time() + seconds
        while time.time() < end:
            t0 = time.perf_counter()
            frame = _capture_raw_and_encode_sync(adb.adb_bin, adb.serial)
            pc_ms.append((time.perf_counter() - t0) * 1000)
            frames += 1 if frame else 0
            time.sleep(max(0.0, interval - (time.perf_counter() - t0)))
    usb_mb = frames * 2.4  # 估算值：RAW 9.3MB/帧，端侧 gzip 后约 2.4MB/帧（gzip 关闭时约 9.3MB）
    return {**s.summary(), "frames": frames, "usb_MB_est": round(usb_mb, 1),
            "pc_ms_per_frame": round(statistics.mean(pc_ms), 1) if pc_ms else 0.0}


def start_scrcpy(adb: Adb):
    subprocess.run([adb.adb_bin, "-s", adb.serial, "push", str(SERVER_LOCAL), SERVER_REMOTE],
                   capture_output=True, timeout=30, check=True)
    subprocess.run([adb.adb_bin, "-s", adb.serial, "forward", f"tcp:{FORWARD_PORT}", f"localabstract:{SOCKET_NAME}"],
                   capture_output=True, timeout=10, check=True)
    args = ["tunnel_forward=true", "audio=false", "control=false", "cleanup=true", "raw_stream=true",
            "max_size=720", "max_fps=10", "video_bit_rate=2000000", "log_level=info"]
    cmd = [adb.adb_bin, "-s", adb.serial, "shell",
           f"CLASSPATH={SERVER_REMOTE}", "app_process", "/", "com.genymobile.scrcpy.Server", SCRCPY_VERSION, *args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    threading.Thread(target=lambda: [print("   [server]", l.decode("utf-8", "replace").rstrip())
                                     for l in proc.stdout], daemon=True).start()
    for _ in range(40):  # server 监听就绪前连接会被立即断开，重试
        time.sleep(0.25)
        try:
            sock = socket.create_connection(("127.0.0.1", FORWARD_PORT), timeout=3)
            sock.settimeout(5)
            first = sock.recv(65536)
            if first:
                return proc, sock, first
            sock.close()
        except OSError:
            continue
    proc.kill()
    raise RuntimeError("scrcpy-server 未能建立视频流，请查看上方 [server] 日志")


def phase_scrcpy(adb: Adb, seconds: float):
    import av
    proc, sock, first = start_scrcpy(adb)
    codec = av.CodecContext.create("h264", "r")
    frames, total_bytes, pc_ms, last_size = 0, 0, [], None
    try:
        with Sampler(adb) as s:
            end, chunk = time.time() + seconds, first
            while time.time() < end:
                if chunk:
                    total_bytes += len(chunk)
                    t0 = time.perf_counter()
                    for packet in codec.parse(chunk):
                        for frame in codec.decode(packet):
                            frames += 1
                            last_size = (frame.width, frame.height)
                    pc_ms.append((time.perf_counter() - t0) * 1000)
                try:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                except socket.timeout:
                    chunk = b""  # 静止画面时编码器不出帧属正常
    finally:
        sock.close()
        proc.kill()
        adb.run("forward", "--remove", f"tcp:{FORWARD_PORT}")
        adb.shell(f"rm -f {SERVER_REMOTE}")
    return {**s.summary(), "frames": frames, "usb_MB": round(total_bytes / 1e6, 2),
            "pc_ms_per_frame": round(sum(pc_ms) / max(1, frames), 1), "frame_size": last_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device")
    ap.add_argument("--seconds", type=float, default=60)
    opts = ap.parse_args()
    if not SERVER_LOCAL.exists():
        sys.exit(f"缺少 {SERVER_LOCAL}")
    adb_bin = AppManager().adb_bin
    serial = opts.device or next(
        (l.split()[0] for l in subprocess.run([adb_bin, "devices"], capture_output=True, text=True).stdout.splitlines()[1:]
         if l.strip().endswith("device")), None)
    if not serial:
        sys.exit("未检测到在线设备")
    adb = Adb(adb_bin, serial)
    adb.shell("input keyevent 224")  # 确保亮屏，各阶段条件一致
    print(f"设备 {serial} | {adb.shell('getprop ro.product.model').strip()} | Android {adb.shell('getprop ro.build.version.release').strip()}")
    print(f"每阶段 {opts.seconds:.0f}s，请保持手机画面静止、不要操作手机\n")

    results = {}
    for name, fn in [("0 基线(亮屏不采集)", lambda: phase_baseline(adb, opts.seconds)),
                     ("1 screencap 每0.8s", lambda: phase_screencap(adb, opts.seconds, 0.8)),
                     ("2 screencap 每3s", lambda: phase_screencap(adb, opts.seconds, 3.0)),
                     ("3 scrcpy 720p@10fps", lambda: phase_scrcpy(adb, opts.seconds))]:
        print(f"▶ 阶段 {name} ...", flush=True)
        try:
            results[name] = fn()
        except Exception as e:
            results[name] = {"error": str(e)}
        print(f"   {results[name]}\n", flush=True)
        time.sleep(5)  # 阶段间冷却

    print("=" * 60)
    for name, r in results.items():
        print(f"{name:22} {r}")


if __name__ == "__main__":
    main()
