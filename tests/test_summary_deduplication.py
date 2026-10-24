import sys
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# 添加工程根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.timeline_manager import TimelineManager
from core.task_manager import TaskManager, SESSIONS_STORE_DIR

def test_backend_summary_deterministic_id_and_singleton():
    print("--- 1. 后端单元测试：测试总结卡片确定性 ID 与单例幂等 ---")
    
    # 验证 block_id 不再含有 uuid
    b1 = TimelineManager.create_test_summary_block(session_id="sess_test_123", turn_id=0)
    b2 = TimelineManager.create_test_summary_block(session_id="sess_test_123", turn_id=0)
    
    print(f"b1 block_id: {b1['block_id']}")
    print(f"b2 block_id: {b2['block_id']}")
    assert b1["block_id"] == "blk_summary_0", f"Expected blk_summary_0, got {b1['block_id']}"
    assert b2["block_id"] == "blk_summary_0", f"Expected blk_summary_0, got {b2['block_id']}"
    assert "_" not in b1["block_id"].replace("blk_summary_0", ""), "block_id should not contain random suffix!"
    print("✅ 校验 1 通过：create_test_summary_block 的 block_id 确定且无随机 UUID！")

    # 验证 get_session 强幂等防重复
    tm = TaskManager()
    session_id = "sess_verify_backend_singleton_001"
    session = {
        "session_id": session_id,
        "title": "测试总结幂等",
        "created_at": "19:27:00",
        "test_mode": "ai",
        "app_filename": None,
        "goal": "验证多次 get_session 不重复生成测试总结",
        "status": "COMPLETED",
        "devices": {},
        "plan_steps": [
            {"id": 1, "title": "步骤1", "desc": "测试", "status": "COMPLETED"}
        ],
        "timeline_blocks": [
            {"type": "user_message", "block_id": "blk_user_0", "turn_id": 0},
            {"type": "test_summary", "block_id": "blk_summary_0", "turn_id": 0, "timestamp": "19:27:19"}
        ]
    }
    tm.sessions[session_id] = session

    # 模拟多次并发或连续 get_session
    s1 = tm.get_session(session_id)
    s2 = tm.get_session(session_id)
    s3 = tm.get_session(session_id)

    summaries = [b for b in s3["timeline_blocks"] if b.get("type") == "test_summary"]
    print(f"Summaries in s3: {len(summaries)}")
    assert len(summaries) == 1, f"Expected exactly 1 test_summary block, got {len(summaries)}"
    print("✅ 校验 2 通过：get_session 强幂等，多次调用始终保持唯一 1 个测试总结块！")


def test_frontend_ui_summary_deduplication():
    print("\n--- 2. 前端端到端 UI 实测：模拟脏数据双总结卡片下的去重拦截 ---")
    artifact_dir = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7")
    out_img = artifact_dir / "verify_summary_deduplication.png"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto("http://127.0.0.1:8000/")
        page.wait_for_timeout(1000)

        # 恶意注入带有两个不同 ID、两个不同时间戳（19:27:19 与 19:27:23）的总结卡片脏数据
        mock_dirty_data = {
            "session_id": "sess_dirty_dual_summary",
            "title": "防重拦截实测会话",
            "goal": "测试当后端或网络存在多张总结卡片时前端是否强制单例去重",
            "status": "COMPLETED",
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
                    "block_id": "blk_step_exec_0_1",
                    "type": "step_execution",
                    "step_id": 1,
                    "title": "Step 1: 进入二手房频道 验证通过 ✅",
                    "status": "COMPLETED",
                    "duration": "0.8s",
                    "actions": []
                },
                # 故意塞入第一张总结卡片（时间戳 19:27:19，带随机 ID A）
                {
                    "block_id": "blk_summary_0_aaaaaa",
                    "type": "test_summary",
                    "turn_id": 0,
                    "session_id": "sess_dirty_dual_summary",
                    "status": "PASS",
                    "goal": "点击二手房入口进入列表",
                    "duration": "152.3s",
                    "steps_summary": "4/4 个关键阶段全部通过",
                    "timestamp": "19:27:19"
                },
                # 故意塞入第二张总结卡片（时间戳 19:27:23，带随机 ID B）
                {
                    "block_id": "blk_summary_0_bbbbbb",
                    "type": "test_summary",
                    "turn_id": 0,
                    "session_id": "sess_dirty_dual_summary",
                    "status": "PASS",
                    "goal": "点击二手房入口进入列表",
                    "duration": "152.3s",
                    "steps_summary": "4/4 个关键阶段全部通过",
                    "timestamp": "19:27:23"
                }
            ]
        }

        # 调用前端渲染函数
        page.evaluate("""(data) => {
            window.activeSessionId = data.session_id;
            window.currentActiveSessionData = data;
            const flow = document.getElementById("messagesFlow");
            if (flow) flow.innerHTML = "";
            window._renderedSessionId = null;
            window._renderedBlockIds = new Set();
            renderChatTimelineStream(data);
        }""", mock_dirty_data)

        page.wait_for_timeout(500)

        # 检查 DOM 中实际存在的 .test-result-summary-card 卡片数量
        summary_count = page.evaluate("() => document.querySelectorAll('.test-result-summary-card').length")
        print(f"DOM 中的总结卡片数量: {summary_count}")
        assert summary_count == 1, f"Expected exactly 1 summary card in DOM, found {summary_count}"
        
        # 验证保留的是最新的 19:27:23 时间戳卡片
        summary_time = page.evaluate("() => document.querySelector('.test-result-summary-card span[style*=\"var(--text-muted)\"]').innerText")
        print(f"保留的总结卡片时间戳: {summary_time}")
        assert summary_time == "19:27:23", f"Expected timestamp 19:27:23, got {summary_time}"

        # 再次触发轮询更新（验证局部更新不会增生）
        page.evaluate("""(data) => {
            renderChatTimelineStream(data);
        }""", mock_dirty_data)
        page.wait_for_timeout(300)

        summary_count_after_poll = page.evaluate("() => document.querySelectorAll('.test-result-summary-card').length")
        print(f"轮询刷新后的总结卡片数量: {summary_count_after_poll}")
        assert summary_count_after_poll == 1, f"Summary cards increased after poll! Got {summary_count_after_poll}"

        page.screenshot(path=str(out_img), full_page=False)
        print(f"✅ 校验 3 通过：前端三重防线成功拦截重复卡片，页面保持绝对单例！截图 -> {out_img}")

        browser.close()

if __name__ == "__main__":
    test_backend_summary_deterministic_id_and_singleton()
    test_frontend_ui_summary_deduplication()
    print("\n🎉 全部单元测试与端到端 UI 防重验证 100% 通过！")
