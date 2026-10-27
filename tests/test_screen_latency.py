# -*- coding: utf-8 -*-
"""
验证真机极速投屏采集延迟、帧率与并发复用性能
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import time
import asyncio
from core.screen_stream_hub import screen_stream_hub, _capture_raw_and_encode_sync
from core.app_manager import AppManager

async def run_latency_benchmark():
    app_mgr = AppManager()
    screen_stream_hub.set_adb_bin(app_mgr.adb_bin)
    
    from core.app_manager import AppManager
    conn = AppManager().get_connected_devices()
    device_id = (conn[0].get("id") if isinstance(conn[0], dict) else conn[0]) if conn else "auto"
    print("=== 开始真机屏幕极速采集性能基准评测 ===")
    
    # 1. 首次采集耗时
    t0 = time.time()
    frame1 = await screen_stream_hub.get_frame(device_id, max_age=0.0)
    t1 = time.time()
    assert frame1 is not None, "首次屏幕捕获失败"
    cost1 = t1 - t0
    mode = frame1.get("mode")
    size_kb = len(frame1.get("jpeg", b"")) / 1024
    print(f"[1] 首次显存直读抓取耗时: {cost1:.3f} 秒 (模式: {mode}, 帧大小: {size_kb:.1f} KB)")
    
    # 2. 内存缓存读取 (预期 < 5ms)
    t2 = time.time()
    frame_cache = await screen_stream_hub.get_frame(device_id, max_age=1.0)
    cost_cache = (time.time() - t2) * 1000
    print(f"[2] 内存缓存复用耗时: {cost_cache:.2f} 毫秒 (0ms 级直出)")
    assert cost_cache < 20, f"缓存读取耗时异常: {cost_cache}ms"
    
    # 3. 连续采集 5 帧测速
    print("[3] 连续采集 5 帧测算平均单帧耗时与稳定帧率:")
    frame_costs = []
    for i in range(5):
        st = time.time()
        f = await asyncio.to_thread(_capture_raw_and_encode_sync, app_mgr.adb_bin, device_id)
        cost = time.time() - st
        frame_costs.append(cost)
        print(f"    - Frame {i+1}: 耗时 {cost:.3f} 秒")
    
    avg_cost = sum(frame_costs) / len(frame_costs)
    fps = 1.0 / avg_cost
    print(f"--> 平均单帧采集+SIMD编码总耗时: {avg_cost:.3f} 秒, 理论帧率: {fps:.2f} FPS")
    
    # 4. 并发 3 客户端同时请求防互锁
    t3 = time.time()
    results = await asyncio.gather(
        screen_stream_hub.get_frame(device_id, max_age=0.05),
        screen_stream_hub.get_frame(device_id, max_age=0.05),
        screen_stream_hub.get_frame(device_id, max_age=0.05)
    )
    cost_concur = time.time() - t3
    print(f"[4] 3 个客户端并发抓取总耗时: {cost_concur:.3f} 秒 (受双重检查锁保护，无通道互锁)")
    assert len(results) == 3 and all(r is not None for r in results)
    
    # 断言：单帧耗时远低于原本的 3.7 秒，且小于 1.1 秒
    assert avg_cost < 1.1, f"单帧耗时超标: {avg_cost:.3f}s"
    print("\n✅ 所有基准测试指标全部达标，真机投屏延迟压缩成功！")

if __name__ == "__main__":
    asyncio.run(run_latency_benchmark())
