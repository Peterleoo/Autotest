# -*- coding: utf-8 -*-
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

artifact_dir = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7")

def verify_agent_flow():
    # 模拟包含语义化动作、耗时、坐标、反馈与阶段断言的会话数据
    mock_session = {
        "session_id": "sess_agent_flow_001",
        "title": "启动应用并处理隐私协议",
        "goal": "启动象盒找房应用，处理首次启动隐私授权弹窗，并成功进入首页",
        "status": "COMPLETED",
        "is_solidified": False,
        "duration": "14.2s",
        "plan_steps": [
            {"id": 1, "title": "启动应用并处理隐私协议", "desc": "点击同意协议并放行", "status": "COMPLETED"}
        ],
        "timeline_blocks": [
            {
                "block_id": "blk_step_1",
                "type": "step_execution",
                "step_id": 1,
                "title": "启动应用并处理隐私协议",
                "status": "COMPLETED",
                "duration": "0.8s",
                "assertion_result": "阶段断言达成: 已成功完成并验证【启动应用并处理隐私协议】",
                "actions": [
                    {
                        "type": "visual",
                        "verb": "视觉感知",
                        "desc": "扫描定位屏幕组件与关键热区 (提取 45 个交互元素)",
                        "param": "OCR: 45 items",
                        "cost_time": "15ms",
                        "status": "COMPLETED",
                        "observation": "视觉多模态感知就绪 · 成功捕获界面组件分布"
                    },
                    {
                        "type": "tap",
                        "verb": "手势点击",
                        "desc": "点击登录体验进入登录界面",
                        "param": "tap(880, 1901)",
                        "cost_time": "18ms",
                        "status": "COMPLETED",
                        "observation": "真机通道响应 18ms · 触控坐标 (880, 1901) [登录体验]",
                        "code_snippet": "driver.tap([(880, 1901)])"
                    },
                    {
                        "type": "visual",
                        "verb": "视觉感知",
                        "desc": "扫描定位屏幕组件与关键热区 (提取 23 个交互元素)",
                        "param": "OCR: 23 items",
                        "cost_time": "15ms",
                        "status": "COMPLETED",
                        "observation": "视觉多模态感知就绪 · 成功捕获界面组件分布"
                    }
                ]
            },
            {
                "block_id": "blk_summary_final",
                "type": "test_summary",
                "turn_id": 0,
                "session_id": "sess_agent_flow_001",
                "status": "PASS",
                "goal": "启动应用并处理隐私协议",
                "duration": "14.2s",
                "steps_summary": "1/1 个关键阶段全部通过",
                "timestamp": "10:18:20"
            }
        ]
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto("http://127.0.0.1:8000/")
        page.wait_for_timeout(1000)

        # 隐藏浮动排查窗
        page.add_style_tag(content="#floatingDeviceWindow { display: none !important; }")

        # 1. 夜间模式
        page.evaluate("""(data) => {
            switchTheme('dark');
            window.activeSessionId = data.session_id;
            window.currentActiveSessionData = data;
            const hero = document.getElementById("welcomeHero");
            if (hero) hero.style.display = "none";
            const cbox = document.getElementById("chatMessagesBox");
            if (cbox) cbox.style.display = "flex";
            const flow = document.getElementById("messagesFlow");
            if (flow) flow.innerHTML = "";
            window._renderedSessionId = null;
            window._renderedBlockIds = new Set();
            window._streamStepState = { "blk_step_1": true }; // 默认展开步骤
            renderChatTimelineStream(data);
        }""", mock_session)
        page.wait_for_timeout(600)

        # 截图全屏夜间
        dark_img = artifact_dir / "verify_agent_flow_dark.png"
        page.screenshot(path=str(dark_img), full_page=False)
        print(f"Captured Dark Mode: {dark_img}")

        # 步骤卡片特写夜间
        step_el = page.locator("#blk_step_1")
        step_dark_img = artifact_dir / "verify_agent_flow_step_closeup_dark.png"
        step_el.screenshot(path=str(step_dark_img))
        print(f"Captured Step Dark Closeup: {step_dark_img}")

        # 顶栏特写夜间
        topbar_el = page.locator(".header-actions")
        topbar_dark_img = artifact_dir / "verify_topbar_icons_dark.png"
        topbar_el.screenshot(path=str(topbar_dark_img))
        print(f"Captured Topbar Dark Closeup: {topbar_dark_img}")

        # 2. 浅色模式
        page.evaluate("""() => {
            switchTheme('light');
        }""")
        page.wait_for_timeout(500)

        light_img = artifact_dir / "verify_agent_flow_light.png"
        page.screenshot(path=str(light_img), full_page=False)
        print(f"Captured Light Mode: {light_img}")

        step_light_img = artifact_dir / "verify_agent_flow_step_closeup_light.png"
        step_el.screenshot(path=str(step_light_img))
        print(f"Captured Step Light Closeup: {step_light_img}")

        browser.close()
        print("Done!")

if __name__ == "__main__":
    verify_agent_flow()
