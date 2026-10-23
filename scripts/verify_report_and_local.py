# -*- coding: utf-8 -*-
import os
import sys
import time
from playwright.sync_api import sync_playwright

def run():
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome_path, headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 950})
        page = context.new_page()
        
        url = "http://127.0.0.1:8000/"
        print(f"Navigating to {url}...")
        page.goto(url)
        page.wait_for_timeout(3000)

        # 切换到浅色主题 (light)
        page.evaluate("() => { if (typeof switchTheme === 'function') switchTheme('light'); }")
        page.wait_for_timeout(1000)

        # 选中目标会话 sess_1022_092344_18c2
        session_id = "sess_1022_092344_18c2"
        print(f"Switching to session {session_id}...")
        page.evaluate(f"() => {{ if (typeof switchSession === 'function') switchSession('{session_id}'); }}")
        page.wait_for_timeout(3500)

        # 确保收起右侧抽屉，以便截取完整的中间流
        page.evaluate("() => { const canvas = document.getElementById('gptCanvas'); if (canvas && !canvas.classList.contains('collapsed')) toggleCanvas(); }")
        page.wait_for_timeout(1000)

        # 滚动中间流到最底部
        page.evaluate("() => { const scroller = document.getElementById('chatScrollArea'); if (scroller) scroller.scrollTop = scroller.scrollHeight; }")
        page.wait_for_timeout(1000)

        # 截图 1：浅色模式 中间层极简流式通知 + 顶栏模式切换器
        shot_path_1 = r"C:\Users\Administrator\.gemini\antigravity\brain\f3ec9076-9983-43bc-abf5-72fe8de4e2b6\minimal_stream_report_light.png"
        page.screenshot(path=shot_path_1, full_page=False)
        print(f"Saved Screenshot 1: {shot_path_1}")

        # 点击交付物文件名超链接打开右侧抽屉
        print("Clicking report filename to open right drawer...")
        page.evaluate("() => { const link = document.querySelector('.report-file-link'); if (link) link.click(); else openReportInRightDrawer(); }")
        page.wait_for_timeout(2000)

        # 截图 2：浅色模式 右侧抽屉滑出展示 6 大维度全景报告 + 顶部保存本地用例
        shot_path_2 = r"C:\Users\Administrator\.gemini\antigravity\brain\f3ec9076-9983-43bc-abf5-72fe8de4e2b6\right_drawer_report_light.png"
        page.screenshot(path=shot_path_2, full_page=False)
        print(f"Saved Screenshot 2: {shot_path_2}")

        # 点击顶栏【本地用例回归】按钮，切换到本地回归看板
        print("Clicking top [本地用例回归] button...")
        page.evaluate("() => { if (typeof switchMainWorkspaceMode === 'function') switchMainWorkspaceMode('local'); }")
        page.wait_for_timeout(2000)

        # 截图 3：浅色模式 本地用例回归看板全景
        shot_path_3 = r"C:\Users\Administrator\.gemini\antigravity\brain\f3ec9076-9983-43bc-abf5-72fe8de4e2b6\local_cases_light.png"
        page.screenshot(path=shot_path_3, full_page=False)
        print(f"Saved Screenshot 3: {shot_path_3}")

        browser.close()
        print("All light screenshots taken successfully!")

if __name__ == "__main__":
    run()
