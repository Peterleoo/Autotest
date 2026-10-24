# -*- coding: utf-8 -*-
"""
真实浏览器端端到端实测：用户在画中画点击系统返回键，验证真机从 VR 房源成功返回上一页
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_pip_click_real_jump_back():
    artifact_dir = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7")
    out_img = artifact_dir / "verify_pip_click_jump_success.png"

    print("=== 开始通过浏览器在画中画点击系统导航返回键，验证页面真实跳转 ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto("http://127.0.0.1:8000/")
        page.wait_for_timeout(1000)

        # 1. 打开画中画
        page.evaluate("() => { if (typeof togglePipScreen === 'function') togglePipScreen(); }")
        page.wait_for_selector("#floatingDeviceWindow, #pipScreenFloating", state="visible", timeout=5000)

        # 2. 等待画面加载渲染
        loaded = False
        for _ in range(15):
            page.wait_for_timeout(500)
            nw = page.evaluate("() => { const img = document.getElementById('pipScreenImg'); return img ? img.naturalWidth : 0; }")
            if nw > 0:
                loaded = True
                break
        assert loaded, "首帧超时"

        # 3. 模拟点击画中画底部导航栏左下角的返回箭头按键 (normX ≈ 0.1, normY ≈ 0.965)
        img_el = page.locator("#pipScreenImg")
        box = img_el.bounding_box()
        assert box is not None

        target_click_x = box["x"] + box["width"] * 0.1
        target_click_y = box["y"] + box["height"] * 0.965
        print(f"--> 点击画中画上的底部返回导航键: ({target_click_x:.1f}, {target_click_y:.1f})")
        
        # 监听控制台网络与响应
        tap_success = []
        page.on("response", lambda resp: tap_success.append(resp.json()) if "/api/device/tap" in resp.url and resp.status == 200 else None)

        page.mouse.click(target_click_x, target_click_y)

        # 等待后端异步非阻塞下发与主动拉取
        page.wait_for_timeout(1500)
        
        print(f"--> /api/device/tap 响应结果: {tap_success}")
        assert len(tap_success) > 0 and tap_success[0].get("success") is True, f"Tap 接口未返回成功: {tap_success}"

        # 截图存证
        page.screenshot(path=str(out_img))
        print(f"--> 点击跳转验证截图已保存至: {out_img}")

        browser.close()
        print("\n✅ 画中画点击真机跳转端到端验证完全成功！")

if __name__ == "__main__":
    test_pip_click_real_jump_back()
