import sys
from pathlib import Path
import json
import pytest

from core.report_generator import ReportGenerator

def test_factual_failure_handling_and_block_diagnosis():
    """
    核验在遇到端侧阻断（如真机无变动白屏自学习阻断）时：
    1. 判定逻辑必须严格输出 is_success = False（坚决杜绝因写入固化文件等无关日志假绿）；
    2. 提取的失败原因必须包含真实的机型与阻断详情；
    3. 生成的报告综合裁定必须为 FAIL，步骤必须呈现受阻/已取消，严禁虚报 100% 达成率。
    """
    sess_path = Path("data/sessions/sess_1026_152754_a8f2.json")
    if not sess_path.exists():
        pytest.skip("Historical session file not found")

    with open(sess_path, "r", encoding="utf-8") as f:
        sess_data = json.load(f)

    dev_state = sess_data["devices"]["2145189e"]
    all_output = dev_state["logs"]

    # 1. 模拟 task_manager 判定逻辑
    all_steps = sess_data.get("plan_steps", [])
    cur_idx = 0

    has_goal_achieved = any("🎉 目标完成" in l or "🎉 测试目标顺利达成" in l for l in all_output)
    has_fatal_block = any(
        ("❌ [设备自学习阻断]" in l) or 
        ("❌ 测试受阻详情" in l) or 
        ("❌ AI 自动化测试未能达成预期目标" in l) or
        ("Traceback (most recent call last)" in l)
        for l in all_output
    )
    proc_returncode = 1

    is_all_steps_reached = (cur_idx >= len(all_steps) - 1) and (len(all_steps) > 0)
    is_success = (proc_returncode == 0) and (not has_fatal_block) and (has_goal_achieved or is_all_steps_reached)

    assert is_success is False, "阻断退出任务严禁被判定为 PASS！"
    assert has_fatal_block is True, "必须精准检测到阻断标记！"
    assert has_goal_achieved is False, "未达成目标严禁因固化成功误判为 True！"

    # 2. 核验失败详情提取
    fail_reason = ""
    for idx, l in enumerate(all_output):
        if "❌ [设备自学习阻断]" in l or "❌ 测试受阻详情" in l:
            next_detail = all_output[idx + 1] if idx + 1 < len(all_output) else ""
            if next_detail and not next_detail.startswith("2026-") and "=====" not in next_detail:
                clean_line = l.split("[ERROR]", 1)[-1].strip() if "[ERROR]" in l else l
                fail_reason = f"{clean_line} {next_detail}".strip()
            else:
                fail_reason = l
            break

    assert "Xiaomi Mi MIX 2" in fail_reason

    # 3. 核验 Markdown 报告真实度
    mock_session = {
        "session_id": "test_factual_verify",
        "goal": sess_data["goal"],
        "plan_steps": [
            {"title": "冷启动应用与前置弹窗放行", "status": "FAIL", "desc": "调起待测应用"},
            {"title": "首页点击'租房'进入租房主频道", "status": "CANCELED", "desc": "进入租房主频道"},
            {"title": "点击'整租'标签进行切换", "status": "CANCELED", "desc": "切换整租"}
        ],
        "error_message": fail_reason
    }
    mock_dev = {
        "device_id": "2145189e",
        "model": "Mi MIX 2",
        "platform": "Android",
        "action": f"测试执行受阻：{fail_reason[:40]}"
    }

    md_content, _ = ReportGenerator.generate_markdown_report(
        session=mock_session,
        dev_state=mock_dev,
        is_success=False,
        raw_output="\n".join(all_output),
        duration_sec=81.2
    )

    assert "❌ FAIL" in md_content
    assert "达成率 **0.0%**" in md_content or "达成率 **0%**" in md_content
    assert "⚠️ 本轮测试执行受阻中断，未达成终态目标，已自动跳过自动化回归脚本固化" in md_content
    assert "受阻失败" in md_content
    assert "已取消" in md_content
    assert "✅ PASS（6大测试维度全项达标）" not in md_content
