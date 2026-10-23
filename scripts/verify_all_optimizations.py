# -*- coding: utf-8 -*-
import os
import sys
import time
from playwright.sync_api import sync_playwright

def run():
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome_path, headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 960})
        page = context.new_page()
        
        url = "http://127.0.0.1:8000/"
        print(f"Navigating to {url}...")
        page.goto(url)
        page.wait_for_timeout(3000)

        # 浅色模式
        page.evaluate("() => { if (typeof switchTheme === 'function') switchTheme('light'); }")
        page.wait_for_timeout(1000)

        # 选中已完成完整链路的会话
        session_id = "sess_1022_092344_18c2"
        print(f"Switching to session {session_id}...")
        page.evaluate(f"() => {{ if (typeof switchSession === 'function') switchSession('{session_id}'); }}")
        page.wait_for_timeout(3500)

        # 滚动到底部，展现测试结果全景总结卡片与结构化产物清单
        page.evaluate("() => { const scroller = document.getElementById('chatScrollArea'); if (scroller) scroller.scrollTop = scroller.scrollHeight; }")
        page.wait_for_timeout(1000)

        # 触发一次触控涟漪演示 (模拟轻触首屏卡片)
        page.evaluate("() => { if (typeof triggerScreenTouchRipple === 'function') triggerScreenTouchRipple(0.5, 0.45, '轻触 房源推荐卡片'); }")
        page.wait_for_timeout(300)

        # 截图 1：流式末尾测试执行总结卡片 + 结构化产物清单 + 投屏触控反馈
        shot_path_1 = r"C:\Users\Administrator\.gemini\antigravity\brain\f3ec9076-9983-43bc-abf5-72fe8de4e2b6\opt_result_summary_and_artifacts.png"
        page.screenshot(path=shot_path_1, full_page=False)
        print(f"Saved Screenshot 1: {shot_path_1}")

        # 切换到本地用例回归看板，验证一键批量回归
        print("Switching to local cases view...")
        page.evaluate("() => { if (typeof switchMainWorkspaceMode === 'function') switchMainWorkspaceMode('local'); }")
        page.wait_for_timeout(2000)

        # 截图 2：本地用例资产看板 + 顶栏【一键批量回归全部】
        shot_path_2 = r"C:\Users\Administrator\.gemini\antigravity\brain\f3ec9076-9983-43bc-abf5-72fe8de4e2b6\opt_batch_regression_local.png"
        page.screenshot(path=shot_path_2, full_page=False)
        print(f"Saved Screenshot 2: {shot_path_2}")

        browser.close()
        print("All optimization verification screenshots taken successfully!")

if __name__ == "__main__":
    run()
