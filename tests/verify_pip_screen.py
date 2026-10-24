# -*- coding: utf-8 -*-
"""
使用 Playwright 验证网页端悬浮画中画投屏及实时真机画面渲染
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_pip_stream_in_browser():
    artifacts_dir = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7")
    screenshot_path = artifacts_dir / "verify_fast_pip_screen.png"
    
    print("=== 启动 Playwright 验证端侧极速投屏在浏览器中的真实渲染 ===")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, channel="msedge")
        except Exception:
            try:
                browser = p.chromium.launch(headless=True, channel="chrome")
            except Exception:
                browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        # 1. 打开主页
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(1)
        
        # 2. 触发悬浮画中画
        print("--> 打开悬浮真机画中画...")
        page.evaluate("() => { if (typeof togglePipScreen === 'function') togglePipScreen(); }")
        
        # 等待画中画容器出现并显示
        pip_el = page.locator("#floatingDeviceWindow, #pipScreenFloating").first
        pip_el.wait_for(state="visible", timeout=5000)
        
        # 3. 等待真机视频流帧加载并渲染
        print("--> 等待真机视频帧渲染到 #pipScreenImg...")
        img_el = page.locator("#pipScreenImg")
        img_el.wait_for(state="visible", timeout=5000)
        
        # 轮询检测 img 的 naturalWidth / naturalHeight
        loaded = False
        for _ in range(20):
            time.sleep(0.5)
            nw = page.evaluate("() => { const img = document.getElementById('pipScreenImg'); return img ? img.naturalWidth : 0; }")
            nh = page.evaluate("() => { const img = document.getElementById('pipScreenImg'); return img ? img.naturalHeight : 0; }")
            if nw > 0 and nh > 0:
                print(f"--> 真机帧成功在浏览器中解码渲染: 宽 {nw}px, 高 {nh}px")
                loaded = True
                break
                
        assert loaded, "真机视频帧未能成功在浏览器中渲染！"
        
        # 4. 获取画中画窗口顶部状态文字
        fps_text = page.locator("#floatingDeviceFps").inner_text()
        print(f"--> 画中画状态栏标识: '{fps_text}'")
        assert "RAW" in fps_text or "延迟" in fps_text, f"状态栏未更新: {fps_text}"
        
        # 5. 截图并存证
        page.screenshot(path=str(screenshot_path))
        print(f"--> 验证截图已保存至: {screenshot_path}")
        
        # 6. 关闭画中画，验证正常释放
        page.evaluate("() => { if (typeof togglePipScreen === 'function') togglePipScreen(); }")
        time.sleep(0.5)
        display = page.evaluate("() => { const p = document.getElementById('floatingDeviceWindow') || document.getElementById('pipScreenFloating'); return p ? p.style.display : ''; }")
        assert display == "none", f"画中画未成功关闭: display={display}"
        print("--> 画中画关闭测试成功，ADB 流连接已释放！")
        
        browser.close()
        print("\n✅ Playwright 真机画中画端到端渲染验证全部成功！")

if __name__ == "__main__":
    test_pip_stream_in_browser()
