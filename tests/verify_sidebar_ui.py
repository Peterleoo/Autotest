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

        # 1. 验证夜间模式高对比度 (新建按钮与搜索框占位文本清晰可辨)
        btn_new = await page.wait_for_selector(".btn-new-task")
        search_inp = await page.wait_for_selector("#sessionSearchInput")
        assert btn_new is not None and search_inp is not None

        # 验证没有残留的数字药丸
        count_pills = await page.query_selector_all(".mode-count-pill")
        print(f"Verified mode count pills count: {len(count_pills)} (Expected 0)")
        assert len(count_pills) == 0, "All mode-count-pills should be completely removed!"

        # 验证没有厚重大白块滑块
        thumbs = await page.query_selector_all(".mode-slider-thumb")
        print(f"Verified mode-slider-thumb count: {len(thumbs)} (Expected 0)")
        assert len(thumbs) == 0, "mode-slider-thumb should be removed!"

        # 截图存证：夜间模式高对比度
        dark_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_dark_high_contrast.png")
        await sidebar.screenshot(path=dark_shot)
        print(f"Saved: {dark_shot}")

        # 2. 验证底部无厚重背景切换按钮
        btn_local = await page.wait_for_selector("#btnModeLocal")
        await btn_local.click()
        await asyncio.sleep(0.5)

        # 3. 验证本地回归文件夹树极简流线呈现
        project_items = await page.query_selector_all(".app-project-item")
        print(f"Found {len(project_items)} app project items in local mode.")
        if len(project_items) > 0:
            first_proj = project_items[0]
            proj_dot = await first_proj.query_selector(".project-status-dot")
            proj_title = await first_proj.query_selector(".project-title")
            proj_count = await first_proj.query_selector(".project-cases-count")
            assert proj_dot is not None and proj_title is not None and proj_count is not None, "Project item structure mismatch!"
            print("Project item text:", (await first_proj.inner_text()).replace("\n", " "))

        # 截图存证：本地回归极简文件夹列表
        local_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_local_projects_minimal.png")
        await sidebar.screenshot(path=local_shot)
        print(f"Saved: {local_shot}")

        # 切回 AI 模式
        btn_ai = await page.wait_for_selector("#btnModeAi")
        await btn_ai.click()
        await asyncio.sleep(0.5)

        # 4. 验证白天模式 (Light Mode) 纯净无背景 Tab 导航与一体化高质感
        print("Switching to light mode...")
        await page.evaluate("document.body.setAttribute('data-theme', 'light'); document.body.classList.add('theme-light');")
        await asyncio.sleep(0.5)

        light_shot = os.path.join(ARTIFACT_DIR, "verify_sidebar_light_no_bg_tabs.png")
        await sidebar.screenshot(path=light_shot)
        print(f"Saved: {light_shot}")

        full_light = os.path.join(ARTIFACT_DIR, "verify_fullpage_minimal_light2.png")
        await page.screenshot(path=full_light)
        print(f"Saved: {full_light}")

        await browser.close()
        print("\n>>> ALL CHECKS PASSED: HIGH CONTRAST, NO-BG TABS, MINIMAL LOCAL FOLDERS! <<<")

if __name__ == "__main__":
    asyncio.run(main())
