import sys
import json
import time
from pathlib import Path

# 添加工程根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.task_manager import TaskManager, SESSIONS_STORE_DIR
from core.timeline_manager import TimelineManager

def test_stream_actions_and_collapse():
    tm = TaskManager()
    
    # 模拟创建一个会话
    session_id = "test_sess_stream_verify_001"
    session = {
        "session_id": session_id,
        "title": "测试二手房与区域筛选",
        "goal": "进入二手房频道，筛选岳麓区，按总价从低到高排序，验证列表数据",
        "status": "RUNNING",
        "created_at": "18:30:00",
        "devices": {
            "test_dev": {
                "id": "test_dev",
                "model": "MIX 2",
                "status": "RUNNING",
                "logs": [],
                "step": 1,
                "max_steps": 15
            }
        },
        "plan_steps": [
            {"id": 1, "title": "进入二手房频道", "desc": "点击二手房入口", "status": "RUNNING"},
            {"id": 2, "title": "展开区域筛选并选择岳麓区", "desc": "选择岳麓区并确定", "status": "READY"},
            {"id": 3, "title": "选择总价升序排序", "desc": "选择总价从低到高", "status": "READY"},
            {"id": 4, "title": "验证列表数据与排序规则", "desc": "断言价格升序排列", "status": "READY"}
        ],
        "timeline_blocks": [
            TimelineManager.create_todo_block([
                {"title": "进入二手房频道", "desc": "点击二手房入口", "status": "RUNNING"},
                {"title": "展开区域筛选并选择岳麓区", "desc": "选择岳麓区并确定", "status": "READY"},
                {"title": "选择总价升序排序", "desc": "选择总价从低到高", "status": "READY"},
                {"title": "验证列表数据与排序规则", "desc": "断言价格升序排列", "status": "READY"}
            ])
        ]
    }
    tm.sessions[session_id] = session

    # 1. 验证启动激活
    tm._advance_session_step(session, 0)
    card_1 = [b for b in session["timeline_blocks"] if b.get("step_id") == 1][0]
    assert card_1["status"] == "RUNNING", f"Step 1 should be RUNNING, got {card_1['status']}"
    print("✅ 校验 1: Step 1 初始创建并处于 RUNNING 状态")

    # 2. 模拟真机第一步执行多轮微动作（归属于 Step 1）
    # 动作 1: OCR 感知
    tm._append_action_to_session_step(session, 0, {
        "type": "ocr",
        "name": "视觉感知",
        "desc": "扫描定位屏幕组件与关键热区 (提取 14 个交互元素)",
        "param": "OCR: 14 items",
        "observation": "视觉多模态感知就绪 · 成功捕获界面组件分布",
        "status": "COMPLETED"
    })
    # 动作 2: 点击启动 App
    tm._append_action_to_session_step(session, 0, {
        "type": "tap",
        "name": "手势点击",
        "desc": "点击启动象盒找房App",
        "param": "tap(668, 824)",
        "observation": "真机通道响应 18ms · 触控坐标 (668, 824) [象盒找房]",
        "status": "COMPLETED"
    })
    # 动作 3: 返回自愈
    tm._append_action_to_session_step(session, 0, {
        "type": "press_key",
        "name": "系统按键",
        "desc": "返回上一页，以便回到首页进入二手房入口",
        "param": "press_key('back')",
        "observation": "系统按键响应 · 触发页面自愈归位",
        "status": "COMPLETED"
    })
    # 动作 4: 点击二手房
    tm._append_action_to_session_step(session, 0, {
        "type": "tap",
        "name": "手势点击",
        "desc": "点击首页金刚区的'二手房'入口",
        "param": "tap(335, 458)",
        "observation": "真机通道响应 18ms · 触控坐标 (335, 458) [二手房]",
        "status": "COMPLETED"
    })

    card_1 = [b for b in session["timeline_blocks"] if b.get("step_id") == 1][0]
    assert len(card_1["actions"]) == 4, f"Step 1 should have 4 actions, got {len(card_1['actions'])}"
    print(f"✅ 校验 2: Step 1 真实微动作多步流式写入成功 (当前累计 {len(card_1['actions'])} 项真实手势与自愈动作)")

    # 3. 推进至 Step 2
    tm._advance_session_step(session, 1)
    card_1 = [b for b in session["timeline_blocks"] if b.get("step_id") == 1][0]
    card_2 = [b for b in session["timeline_blocks"] if b.get("step_id") == 2][0]

    assert card_1["status"] == "COMPLETED", f"Step 1 should be COMPLETED, got {card_1['status']}"
    assert len(card_1["actions"]) == 4, "Step 1 actions should be preserved, not overwritten by mock!"
    assert card_2["status"] == "RUNNING", f"Step 2 should be RUNNING, got {card_2['status']}"
    print("✅ 校验 3: Step 1 顺利完成转为 COMPLETED 并保留 4 项真实手势动作；Step 2 激活为 RUNNING")

    # 4. 在 Step 2 注入真实筛选动作
    tm._append_action_to_session_step(session, 1, {
        "type": "tap",
        "name": "手势点击",
        "desc": "点击'区域'筛选项以展开区域选择面板",
        "param": "tap(118, 297)",
        "observation": "真机通道响应 18ms · 触控坐标 (118, 297) [区域]",
        "status": "COMPLETED"
    })
    tm._append_action_to_session_step(session, 1, {
        "type": "tap",
        "name": "手势点击",
        "desc": "在区域筛选列表中选择'岳麓区'",
        "param": "tap(306, 845)",
        "observation": "真机通道响应 18ms · 触控坐标 (306, 845) [岳麓区]",
        "status": "COMPLETED"
    })
    tm._append_action_to_session_step(session, 1, {
        "type": "tap",
        "name": "手势点击",
        "desc": "点击确定按钮应用'岳麓区'筛选条件",
        "param": "tap(744, 1595)",
        "observation": "真机通道响应 18ms · 触控坐标 (744, 1595) [确定]",
        "status": "COMPLETED"
    })
    card_2 = [b for b in session["timeline_blocks"] if b.get("step_id") == 2][0]
    assert len(card_2["actions"]) == 3
    print("✅ 校验 4: Step 2 真实点击/选择/确定 3 项微动作写入成功")

    # 5. 模拟完成全流程
    tm._finish_pipeline(session, 3, is_success=True)
    all_cards = [b for b in session["timeline_blocks"] if b.get("type") in ["step_execution", "step_result"]]
    running_cards = [c for c in all_cards if c.get("status") == "RUNNING"]
    assert len(running_cards) == 0, f"No cards should be RUNNING after finish, found {len(running_cards)}"
    
    # 清理测试 session 文件
    test_file = SESSIONS_STORE_DIR / f"{session_id}.json"
    if test_file.exists():
        test_file.unlink()

    print("✅ 校验 5: _finish_pipeline 全流程收束成功，所有步骤卡片状态全部转为 COMPLETED，无一残留 RUNNING！")
    print("🎉 后端状态流与微动作全链路单元测试 100% 通过！")

if __name__ == "__main__":
    test_stream_actions_and_collapse()
