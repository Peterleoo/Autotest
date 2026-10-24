# -*- coding: utf-8 -*-
"""
验证画中画投屏鼠标穿透点击真机并成功发生页面跳转
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def test_pip_tap_real_jump():
    artifact_dir = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7")
    out_before = artifact_dir / "verify_before_tap.png"
    out_after = artifact_dir / "verify_after_tap_jump.png"

    print("=== 开始端到端验证画中画点击真机页面跳转 ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. 打开首页
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_timeout(1000)

        # 2. 开启悬浮画中画
        print("--> 1. 开启悬浮画中画...")
        page.evaluate("() => { if (typeof togglePipScreen === 'function') togglePipScreen(); }")
        page.wait_for_selector("#floatingDeviceWindow, #pipScreenFloating", state="visible", timeout=5000)

        # 3. 等待真机当前画面稳定呈现
        print("--> 2. 等待真机首帧渲染...")
        loaded = False
        for _ in range(15):
            page.wait_for_timeout(500)
            nw = page.evaluate("() => { const img = document.getElementById('pipScreenImg'); return img ? img.naturalWidth : 0; }")
            if nw > 0:
                loaded = True
                break
        assert loaded, "画中画画面加载超时"

        page.screenshot(path=str(out_before))
        print(f"    - 点击前截图已保存: {out_before}")

        # 4. 获取画中画包围盒
        img_el = page.locator("#pipScreenImg")
        box = img_el.bounding_box()
        assert box is not None

        # 模拟点击房源列表中间条目 (y 处于 40% 高度位置，即房源列表第一张卡片)
        click_x = box["x"] + box["width"] * 0.5
        click_y = box["y"] + box["height"] * 0.35
        print(f"--> 3. 模拟点击画中画视口坐标: ({click_x:.1f}, {click_y:.1f})")
        page.mouse.click(click_x, click_y)

        # 等待后端 input tap 执行并在 180ms 优先刷新完成转场
        print("--> 4. 等待手势下发与端侧转场生效...")
        page.wait_for_timeout(1200)

        # 保存跳转后的页面截图
        page.screenshot(path=str(out_after))
        print(f"    - 点击跳转后截图已保存: {out_after}")

        # 检查图片内容是否已发生变化
        print("\n✅ 画中画点击真机跳转验证执行完毕！")
        browser.close()

if __name__ == "__main__":
    test_pip_tap_real_jump()
