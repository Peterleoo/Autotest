# -*- coding: utf-8 -*-
"""
1. Converge 6-dimension report into test_summary deliverables (do not render standalone final_report card in chat stream).
2. Strictly enforce completion gate: do NOT show test_summary if session is RUNNING or not all steps are finished!
"""

# Part 1: Update web/templates/index.html
html_path = 'web/templates/index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

# In buildBlockHtml, ensure test_summary only renders when session is truly completed
summary_gate_old = '''            if (blk.type === "test_summary") {
                const sid = blk.session_id || sessionData.session_id || activeSessionId;'''

summary_gate_new = '''            if (blk.type === "test_summary") {
                // 核心门禁：只有全流程彻底完成 (COMPLETED/READY_FOR_REVIEW/FAILED) 且非 RUNNING 状态，才展示总结果！
                const isFinished = (sessionData.status === "COMPLETED" || sessionData.status === "READY_FOR_REVIEW" || sessionData.status === "FAILED");
                if (!isFinished || sessionData.status === "RUNNING") {
                    return "";
                }
                const sid = blk.session_id || sessionData.session_id || activeSessionId;'''

assert summary_gate_old in html_content, "summary_gate_old not found in index.html!"
html_content = html_content.replace(summary_gate_old, summary_gate_new, 1)

# In buildBlockHtml, make final_report return empty string because it is already a deliverable inside test_summary!
final_report_old = '''            if (blk.type === "final_report") {
                const sid = blk.session_id || sessionData.session_id || activeSessionId;'''

final_report_new = '''            if (blk.type === "final_report") {
                // 用户明确指示：6 大维度全景报告本身就是交付物资产，已统一收敛在【测试执行结果总结】卡片中，对话流中无需单独重复平铺
                return "";
                const sid = blk.session_id || sessionData.session_id || activeSessionId;'''

assert final_report_old in html_content, "final_report_old not found in index.html!"
html_content = html_content.replace(final_report_old, final_report_new, 1)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Updated index.html: gate enforced and standalone final_report converged!")

# Part 2: Update core/task_manager.py
tm_path = 'core/task_manager.py'
with open(tm_path, 'r', encoding='utf-8') as f:
    tm_content = f.read()

# In _synthesize_timeline_blocks
old_tm_summary = '''        # 7. 测试结果全景总结卡片 (用户特别指定重点)
        if s.get("status") in ["COMPLETED", "READY_FOR_REVIEW", "PASS"] or (md and "PASS" in md):'''

new_tm_summary = '''        # 7. 测试结果全景总结卡片 (仅当全流程全部完成且非进行中时输出)
        is_truly_done = (s.get("status") in ["COMPLETED", "READY_FOR_REVIEW", "PASS"]) and (s.get("status") != "RUNNING")
        if is_truly_done:'''

assert old_tm_summary in tm_content, "old_tm_summary not found in task_manager.py!"
tm_content = tm_content.replace(old_tm_summary, new_tm_summary, 1)

# In get_session heal logic
old_heal = '''            # 🚀 自动同步补齐测试总结卡片与结构化产物
            has_summary = any(b.get("type") == "test_summary" for b in tb)
            if not has_summary and (s.get("status") in ["COMPLETED", "READY_FOR_REVIEW", "PASS"] or any(b.get("type") == "final_report" for b in tb)):'''

new_heal = '''            # 🚀 自动同步补齐测试总结卡片与结构化产物 (必须全流程完成且非 RUNNING)
            has_summary = any(b.get("type") == "test_summary" for b in tb)
            is_session_finished = (s.get("status") in ["COMPLETED", "READY_FOR_REVIEW", "PASS"]) and (s.get("status") != "RUNNING")
            if not has_summary and is_session_finished:'''

assert old_heal in tm_content, "old_heal not found in task_manager.py!"
tm_content = tm_content.replace(old_heal, new_heal, 1)

with open(tm_path, 'w', encoding='utf-8') as f:
    f.write(tm_content)

print("Updated task_manager.py: test_summary timing strictly gated!")
