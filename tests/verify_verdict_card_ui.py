# -*- coding: utf-8 -*-
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

artifact_dir = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7")

def verify_clean_ui():
    mock_session = {
        "session_id": "sess_verdict_verify_001",
        "title": "二手房升序排序测试",
        "goal": "进入二手房列表，选择总价升序排列并断言房源数据",
        "status": "COMPLETED",
        "is_solidified": False,
        "duration": "152.3s",
        "plan_steps": [
            {"id": 1, "title": "进入二手房频道", "desc": "点击二手房入口", "status": "COMPLETED"},
            {"id": 2, "title": "展开区域筛选并选择岳麓区", "desc": "选择岳麓区并确定", "status": "COMPLETED"},
            {"id": 3, "title": "选择总价升序排序", "desc": "选择总价从低到高", "status": "COMPLETED"},
            {"id": 4, "title": "验证列表数据与排序规则", "desc": "断言价格升序排列", "status": "COMPLETED"}
        ],
        "timeline_blocks": [
            {
                "block_id": "blk_todo_001",
                "type": "todo_list",
                "title": "任务清单",
                "completed_count": 4,
                "total_count": 4,
                "items": [
                    {"title": "进入二手房频道", "desc": "点击二手房入口", "status": "COMPLETED"},
                    {"title": "展开区域筛选并选择岳麓区", "desc": "选择岳麓区并确定", "status": "COMPLETED"},
                    {"title": "选择总价升序排序", "desc": "选择总价从低到高", "status": "COMPLETED"},
                    {"title": "验证列表数据与排序规则", "desc": "断言价格升序排列", "status": "COMPLETED"}
                ]
            },
            {
                "block_id": "blk_step_1",
                "type": "step_execution",
                "step_id": 1,
                "title": "Step 1: 进入二手房频道 验证通过 ✅",
                "status": "COMPLETED",
                "duration": "0.8s",
                "actions": [
                    {"type": "tap", "verb": "点击", "target": "二手房入口", "cost_time": "18ms", "status": "COMPLETED"}
                ]
            },
            {
                "block_id": "blk_step_2",
                "type": "step_execution",
                "step_id": 2,
                "title": "Step 2: 展开区域筛选并选择岳麓区",
                "status": "COMPLETED",
                "duration": "1.2s",
                "actions": [
                    {"type": "tap", "verb": "点击", "target": "区域筛选", "cost_time": "22ms", "status": "COMPLETED"},
                    {"type": "tap", "verb": "选择", "target": "岳麓区", "cost_time": "19ms", "status": "COMPLETED"}
                ]
            },
            {
                "block_id": "blk_step_3",
                "type": "step_execution",
                "step_id": 3,
                "title": "Step 3: 选择总价升序排序",
                "status": "COMPLETED",
                "duration": "0.9s",
                "actions": [
                    {"type": "tap", "verb": "点击", "target": "排序", "cost_time": "15ms", "status": "COMPLETED"}
                ]
            },
            {
                "block_id": "blk_step_4",
                "type": "step_execution",
                "step_id": 4,
                "title": "Step 4: 验证列表数据与排序规则",
                "status": "COMPLETED",
                "duration": "1.4s",
                "assertion_result": "房源总价按升序单调递增，数据校验通过",
                "actions": [
                    {"type": "assert", "verb": "校验", "target": "房源列表升序", "cost_time": "45ms", "status": "COMPLETED"}
                ]
            },
            {
                "block_id": "blk_summary_final",
                "type": "test_summary",
                "turn_id": 0,
                "session_id": "sess_verdict_verify_001",
                "status": "PASS",
                "goal": "二手房升序排序测试",
                "duration": "152.3s",
                "steps_summary": "4/4 个关键阶段全部通过",
                "timestamp": "19:27:23"
            }
        ]
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto("http://127.0.0.1:8000/")
        page.wait_for_timeout(1000)

        # 注入全局 CSS 隐藏遮挡测试工作台的浮窗，方便产出纯净的 UI 存证图
        page.add_style_tag(content="#floatingDeviceWindow { display: none !important; }")

        # 1. 注入夜间模式并渲染数据
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
            renderChatTimelineStream(data);

            const card = document.querySelector(".test-result-summary-card");
            if (card) {
                card.scrollIntoView({ behavior: "instant", block: "center" });
            }
        }""", mock_session)
        page.wait_for_timeout(500)

        dark_img = artifact_dir / "verify_verdict_card_dark.png"
        page.screenshot(path=str(dark_img), full_page=False)
        print(f"Captured Dark Mode: {dark_img}")

        card_el = page.locator(".test-result-summary-card")
        card_dark_img = artifact_dir / "verify_verdict_card_closeup_dark.png"
        card_el.screenshot(path=str(card_dark_img))
        print(f"Captured Card Dark Closeup: {card_dark_img}")

        # 2. 切换为白天模式并截图
        page.evaluate("""() => {
            switchTheme('light');
            const card = document.querySelector(".test-result-summary-card");
            if (card) {
                card.scrollIntoView({ behavior: "instant", block: "center" });
            }
        }""")
        page.wait_for_timeout(500)

        light_img = artifact_dir / "verify_verdict_card_light.png"
        page.screenshot(path=str(light_img), full_page=False)
        print(f"Captured Light Mode: {light_img}")

        card_light_img = artifact_dir / "verify_verdict_card_closeup_light.png"
        card_el.screenshot(path=str(card_light_img))
        print(f"Captured Card Light Closeup: {card_light_img}")

        browser.close()
        print("Done!")

if __name__ == "__main__":
    verify_clean_ui()
