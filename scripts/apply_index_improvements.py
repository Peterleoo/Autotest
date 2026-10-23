import re
from pathlib import Path

BASE_DIR = Path("F:/Autotest")
html_path = BASE_DIR / "web/templates/index.html"
html_code = html_path.read_text(encoding="utf-8")

# 1. 强化 test_summary 门禁：必须所有 steps 100% 完成
old_summary_gate = '''            if (blk.type === "test_summary") {
                // 核心门禁：只有全流程彻底完成 (COMPLETED/READY_FOR_REVIEW/FAILED) 且非 RUNNING 状态，才展示总结果！
                const isFinished = (sessionData.status === "COMPLETED" || sessionData.status === "READY_FOR_REVIEW" || sessionData.status === "FAILED");
                if (!isFinished || sessionData.status === "RUNNING") {
                    return "";
                }'''

new_summary_gate = '''            if (blk.type === "test_summary") {
                // 核心门禁：只有全流程彻底完成，且任务清单所有步骤 100% 达成，且非 RUNNING 状态，才展示总结果！
                const isFinished = (sessionData.status === "COMPLETED" || sessionData.status === "READY_FOR_REVIEW" || sessionData.status === "FAILED");
                const steps = sessionData.plan_steps || [];
                const total = steps.length;
                const completed = steps.filter(s => s.status === "COMPLETED" || s.status === "PASS").length;
                const isAllStepsDone = (total > 0 && completed === total);
                
                if (!isFinished || sessionData.status === "RUNNING" || !isAllStepsDone) {
                    return "";
                }'''

if old_summary_gate in html_code:
    html_code = html_code.replace(old_summary_gate, new_summary_gate)
    print("Replaced summary gate in index.html successfully.")
else:
    print("WARNING: Could not find old_summary_gate in index.html")

# 2. 增强动作流渲染：支持进行中动画与反馈
old_action_row = '''                        <div class="step-micro-action-row">
                            <div class="d-flex align-items-center gap-2">
                                <span class="action-seq-badge">${actIdx + 1}</span>
                                <span class="action-call-text"><strong>${escapeHtml(act.name || '动作')}</strong>: ${escapeHtml(act.desc || act.action || '')}</span>
                                ${act.param ? `<span class="mono-pill" style="font-size: 9.5px;">${escapeHtml(act.param)}</span>` : ''}
                            </div>
                            <div class="action-observation-text">
                                <span class="obs-arrow">↳</span>
                                <span class="obs-label">获得反馈：</span>
                                <span>${escapeHtml(act.observation || act.detail || '屏幕状态响应就绪')}</span>
                            </div>
                        </div>'''

new_action_row = '''                        <div class="step-micro-action-row ${act.status === 'RUNNING' ? 'action-running' : ''}">
                            <div class="d-flex align-items-center gap-2">
                                <span class="action-seq-badge">${actIdx + 1}</span>
                                <span class="action-call-text"><strong>${escapeHtml(act.name || '动作')}</strong>: ${escapeHtml(act.desc || act.action || '')}</span>
                                ${act.status === 'RUNNING' ? `<span class="mono-pill" style="font-size: 9px; color: var(--status-green); background: var(--status-green-bg);"><i class="bi bi-arrow-repeat spin me-1"></i>执行中</span>` : ''}
                                ${act.param ? `<span class="mono-pill" style="font-size: 9.5px;">${escapeHtml(act.param)}</span>` : ''}
                            </div>
                            <div class="action-observation-text">
                                <span class="obs-arrow">↳</span>
                                <span class="obs-label">获得反馈：</span>
                                <span>${act.status === 'RUNNING' ? '<i class=\"bi bi-hourglass-split me-1 text-muted\"></i>' : ''}${escapeHtml(act.observation || act.detail || '屏幕状态响应就绪')}</span>
                            </div>
                        </div>'''

if old_action_row in html_code:
    html_code = html_code.replace(old_action_row, new_action_row)
    print("Replaced old_action_row in index.html successfully.")
else:
    print("WARNING: Could not find old_action_row in index.html")

# 同样替换 8864 行附近的那个动作行
old_action_row_2 = '''                        <div class="step-micro-action-row">
                            <div class="d-flex align-items-center gap-2">
                                <span class="action-seq-badge">${actIdx + 1}</span>
                                <span class="action-call-text"><strong>${escapeHtml(act.name || '调用动作')}</strong>: ${escapeHtml(act.desc || act.action || '')}</span>
                                ${act.param ? `<span class="mono-pill" style="font-size: 9.5px;">${escapeHtml(act.param)}</span>` : ''}
                            </div>
                            <div class="action-observation-text">
                                <span class="obs-arrow">↳</span>
                                <span class="obs-label">获得反馈：</span>
                                <span>${escapeHtml(act.observation || act.detail || '屏幕状态响应就绪')}</span>
                            </div>
                        </div>'''

if old_action_row_2 in html_code:
    html_code = html_code.replace(old_action_row_2, new_action_row)
    print("Replaced old_action_row_2 in index.html successfully.")
else:
    print("WARNING: Could not find old_action_row_2 in index.html")

html_path.write_text(html_code, encoding="utf-8")
print("index.html saved successfully.")
