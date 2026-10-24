# -*- coding: utf-8 -*-
import os
import asyncio
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="msedge")
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navigating to http://127.0.0.1:8000/ ...")
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await asyncio.sleep(1.5)

        sidebar = await page.wait_for_selector("#gptSidebar", timeout=5000)
        assert sidebar is not None, "Sidebar not found!"

        # 1. 验证新建任务 Hero 按钮与快捷键
        btn_new = await page.wait_for_selector(".btn-new-task")
        print("Hero CTA button text:", (await btn_new.inner_text()).replace("\n", " "))

        # 2. 验证单行极简条目（无机器名、无 PASS/FAIL 堆叠标签）
        items = await page.query_selector_all(".session-item")
        print(f"Found {len(items)} active session items in open groups.")
        assert len(items) > 0, "No session items found!"
        
        # 确认页面内不存在多余的 session-meta-pill
        pills = await page.query_selector_all(".session-meta-pill")
        print(f"Verified redundant badges count: {len(pills)} (Expected 0)")
        assert len(pills) == 0, "Redundant session-meta-pill badges should be removed!"

        # 3. 验证圆点状态与悬浮操作
        first_item = items[0]
        dot = await first_item.query_selector(".session-status-dot")
        assert dot is not None, "Status dot not found!"
        
        await first_item.hover()
        await asyncio.sleep(0.3)
        actions = await first_item.query_selector(".session-actions")
        assert actions is not None, "Actions not found on hover!"

        # 截图深色极简侧边栏
        dark_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_minimal_dark.png")
        await sidebar.screenshot(path=dark_shot)
        print(f"Saved: {dark_shot}")

        # 4. 验证时间累计分组一键折叠与展开
        print("Testing collapsible time groups...")
        headers = await page.query_selector_all(".session-group-header")
        assert len(headers) > 0, "No group headers found!"
        today_header = headers[0]
        header_text = await today_header.inner_text()
        print(f"Toggling first header: {header_text.replace(chr(10), ' ')}")

        # 点击折叠“今天”
        count_before = len(await page.query_selector_all(".session-item"))
        await today_header.click()
        await asyncio.sleep(0.4)
        count_after = len(await page.query_selector_all(".session-item"))
        print(f"Items count before toggle: {count_before}, after collapse: {count_after}")
        assert count_after < count_before, "Items in collapsed group should be hidden!"

        # 截图折叠状态
        collapse_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_collapsed_group.png")
        await sidebar.screenshot(path=collapse_shot)
        print(f"Saved: {collapse_shot}")

        # 再次点击展开“今天”
        new_headers = await page.query_selector_all(".session-group-header")
        await new_headers[0].click()
        await asyncio.sleep(0.4)
        count_restored = len(await page.query_selector_all(".session-item"))
        print(f"Items count restored: {count_restored}")
        assert count_restored == count_before, "Items count should be fully restored on expand!"

        # 5. 验证底部胶囊：苹果流体物理滑动滑块
        print("Testing Apple liquid sliding segmented control...")
        switcher = await page.wait_for_selector("#sidebarModeSwitcher")
        thumb = await page.wait_for_selector("#modeSliderThumb")
        assert switcher is not None and thumb is not None, "Mode switcher or thumb missing!"

        # 点击本地回归
        btn_local = await page.wait_for_selector("#btnModeLocal")
        await btn_local.click()
        await asyncio.sleep(0.5)

        # 检查 switcher 是否包含 is-local
        switcher_classes = await switcher.get_attribute("class")
        print("Switcher classes after clicking local:", switcher_classes)
        assert "is-local" in switcher_classes, "Switcher should have 'is-local' class!"

        # 截图滑块滑动到右侧的状态
        slide_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_sliding_switcher.png")
        await sidebar.screenshot(path=slide_shot)
        print(f"Saved: {slide_shot}")

        # 切回 AI 模式
        btn_ai = await page.wait_for_selector("#btnModeAi")
        await btn_ai.click()
        await asyncio.sleep(0.5)
        switcher_classes_ai = await switcher.get_attribute("class")
        print("Switcher classes after clicking AI:", switcher_classes_ai)
        assert "is-local" not in switcher_classes_ai, "Switcher should not have 'is-local' class in AI mode!"

        # 6. 验证白天模式 (Light Mode) 色彩与协调度
        print("Testing light mode aesthetics and harmony...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.5)

        light_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_minimal_light.png")
        await sidebar.screenshot(path=light_shot)
        print(f"Saved: {light_shot}")

        full_light = os.path.join(ARTIFACT_DIR, "verify_fullpage_minimal_light.png")
        await page.screenshot(path=full_light)
        print(f"Saved: {full_light}")

        await browser.close()
        print("\n>>> ALL MINIMALIST REDESIGN TESTS PASSED WITH 100% SUCCESS! <<<")

if __name__ == "__main__":
    asyncio.run(main())
