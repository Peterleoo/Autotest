# -*- coding: utf-8 -*-
import time
import urllib.request

def test_screenshot_http():
    print("=== 开始端到端 HTTP 接口性能验证 ===")
    
    # 1. 抓取第一帧 (触发极速采集)
    t0 = time.time()
    req = urllib.request.Request("http://127.0.0.1:8000/api/devices/2145189e/screenshot?format=jpeg")
    with urllib.request.urlopen(req, timeout=5) as resp:
        data1 = resp.read()
        cost1 = time.time() - t0
        ct1 = resp.headers.get("Content-Type")
        print(f"[HTTP-1] 首次截图抓取: 状态 {resp.status}, 类型: {ct1}, 帧大小: {len(data1)/1024:.1f} KB, 耗时: {cost1:.3f} 秒")
        assert resp.status == 200
        assert "image/jpeg" in ct1
        assert len(data1) > 1000

    # 2. 立即发起第二次请求 (验证内存快速复用)
    t1 = time.time()
    with urllib.request.urlopen(req, timeout=5) as resp:
        data2 = resp.read()
        cost2 = (time.time() - t1) * 1000
        print(f"[HTTP-2] 立即二次请求: 耗时 {cost2:.2f} 毫秒")
        assert resp.status == 200
        assert cost2 < 1000, f"单帧响应耗时过长: {cost2}ms"

    # 3. 验证 MJPEG 实时帧流接口
    print("[HTTP-3] 验证 MJPEG 实时帧流接口:")
    stream_req = urllib.request.Request("http://127.0.0.1:8000/api/device/screen/stream?device_id=2145189e")
    t2 = time.time()
    with urllib.request.urlopen(stream_req, timeout=8) as resp:
        stream_ct = resp.headers.get("Content-Type")
        print(f"    - 流响应状态: {resp.status}, 媒体类型: {stream_ct}")
        assert resp.status == 200
        assert "multipart/x-mixed-replace" in stream_ct
        
        # 读取前 3 帧
        buffer = b""
        frames_received = 0
        while frames_received < 3:
            chunk = resp.read(8192)
            if not chunk:
                break
            buffer += chunk
            while b"--frame\r\n" in buffer:
                parts = buffer.split(b"--frame\r\n", 1)
                buffer = parts[1]
                frames_received += 1
                now_cost = time.time() - t2
                print(f"    - 成功接收并消费帧 #{frames_received}, 累计耗时: {now_cost:.3f} 秒")
                t2 = time.time()
                
    print("\n✅ 端到端 HTTP 接口性能验证全部通过！")

if __name__ == "__main__":
    test_screenshot_http()
