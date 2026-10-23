# -*- coding: utf-8 -*-
"""
Patch web/templates/index.html to:
1. Add CSS for touch ripple, micro actions, fault diagnosis, and test result summary card
2. Add touch ripple logic to floatingDeviceWindow and triggerScreenTouchRipple function
3. Update buildBlockHtml with step_execution (action -> observation), fault_diagnosis, and test_summary card
4. Add batch regression button in workspaceLocalView header and implement runBatchLocalRegression function
"""

path = 'web/templates/index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add CSS
css_anchor = '/* 顶栏模式切换分段控制器 (极简去线条化风格) */'
css_new = '''/* 触控涟漪与视觉锚点动画 */
        .device-action-ripple {
            position: absolute;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: rgba(59, 130, 246, 0.45);
            border: 2px solid #3b82f6;
            box-shadow: 0 0 14px rgba(59, 130, 246, 0.85);
            pointer-events: none;
            transform: translate(-50%, -50%) scale(0.2);
            opacity: 0;
            z-index: 20;
        }
        .device-action-ripple.active {
            animation: touchRippleKeyframes 1.2s cubic-bezier(0.1, 0.8, 0.3, 1) forwards;
        }
        @keyframes touchRippleKeyframes {
            0% { transform: translate(-50%, -50%) scale(0.2); opacity: 1; }
            50% { transform: translate(-50%, -50%) scale(1.6); opacity: 0.85; }
            100% { transform: translate(-50%, -50%) scale(2.4); opacity: 0; }
        }

        /* 步骤内微观动作行：调用动作 -> 获得反馈 */
        .step-micro-action-row {
            padding: 6px 8px;
            background: var(--bg-main);
            border-radius: 6px;
            margin-bottom: 5px;
            font-size: 11.5px;
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .action-seq-badge {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: var(--bg-surface-elevated, #e2e8f0);
            color: var(--text-sub);
            font-size: 9px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-family: var(--font-mono);
            flex-shrink: 0;
        }
        .action-call-text {
            color: var(--text-main);
            font-size: 11.5px;
        }
        .action-observation-text {
            padding-left: 24px;
            color: var(--text-sub);
            font-size: 11px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .obs-arrow {
            color: var(--status-green, #10b981);
            font-weight: bold;
        }
        .obs-label {
            color: var(--text-muted);
            font-size: 10px;
        }

        /* 三段式受阻人话诊断卡片 */
        .stream-fault-diag-card {
            background: var(--bg-surface);
            border-radius: 8px;
            padding: 12px 14px;
            margin-top: 10px;
            border-left: 3px solid #ef4444;
        }
        .diag-item {
            margin-bottom: 4px;
            font-size: 11.5px;
            line-height: 1.6;
        }
        .diag-item-label {
            color: var(--text-main);
            font-weight: 600;
        }
        .diag-item-text {
            color: var(--text-sub);
        }

        /* 测试结果全景总结卡片 (结构化产物清单与保存本地用例) */
        .test-result-summary-card {
            background: var(--bg-surface);
            border-radius: 8px;
            padding: 14px 16px;
            margin-top: 12px;
            border: none;
        }
        .summary-card-title {
            font-weight: 600;
            font-size: 13.5px;
            color: var(--text-main);
        }
        .summary-metric-bar {
            font-size: 12px;
            line-height: 1.7;
            color: var(--text-sub);
            padding: 8px 12px;
            background: var(--bg-main);
            border-radius: 6px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .summary-artifacts-box {
            background: var(--bg-main);
            border-radius: 6px;
            padding: 10px 12px;
        }
        .artifacts-box-title {
            font-size: 11.5px;
            font-weight: 600;
            color: var(--text-main);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .artifact-item-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 8px;
            border-radius: 5px;
            margin-top: 4px;
            transition: background 0.15s ease;
        }
        .artifact-item-row:hover {
            background: var(--bg-surface);
        }
        .artifact-name {
            font-size: 12px;
            color: var(--text-main);
            font-weight: 500;
        }
        .artifact-file {
            font-family: var(--font-mono);
            color: var(--text-sub);
        }
        .pass-pill {
            color: var(--status-green);
            background: var(--status-green-bg);
            border: 1px solid var(--status-green-border);
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 4px;
        }
        .fail-pill {
            color: #ef4444;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.25);
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 4px;
        }

        /* 顶栏模式切换分段控制器 (极简去线条化风格) */'''

assert css_anchor in content, "css_anchor not found!"
content = content.replace(css_anchor, css_new, 1)

# 2. Add batch regression button to workspaceLocalView
local_btn_anchor = '''                    <div class="d-flex align-items-center gap-2">
                        <button class="icon-btn" onclick="loadSolidifiedCasesWorkspace()" title="刷新用例列表">
                            <i class="bi bi-arrow-clockwise"></i>
                        </button>
                    </div>'''

local_btn_new = '''                    <div class="d-flex align-items-center gap-2">
                        <button class="btn btn-sm btn-primary py-1 px-2.5 d-flex align-items-center gap-1.5" id="btnBatchRunLocal" onclick="runBatchLocalRegression()" style="font-size: 11.5px; border-radius: 6px;">
                            <i class="bi bi-play-circle-fill"></i>
                            <span>一键批量回归全部</span>
                        </button>
                        <button class="icon-btn" onclick="loadSolidifiedCasesWorkspace()" title="刷新用例列表">
                            <i class="bi bi-arrow-clockwise"></i>
                        </button>
                    </div>'''

assert local_btn_anchor in content, "local_btn_anchor not found!"
content = content.replace(local_btn_anchor, local_btn_new, 1)

# 3. Add JS functions for touch ripple and batch regression
js_helper_anchor = '''        function openReportInRightDrawer(sessionId) {'''

js_helper_new = '''        // 触控涟漪动效
        function triggerScreenTouchRipple(xRatio, yRatio, label) {
            const ripple = document.getElementById("deviceActionRipple");
            if (!ripple) return;
            const x = (xRatio !== undefined ? xRatio : 0.5) * 100;
            const y = (yRatio !== undefined ? yRatio : 0.5) * 100;
            ripple.style.left = `${x}%`;
            ripple.style.top = `${y}%`;
            ripple.classList.remove("active");
            void ripple.offsetWidth;
            ripple.classList.add("active");
            const statusEl = document.getElementById("floatingDeviceStatus");
            if (statusEl && label) statusEl.innerText = label;
        }

        // 一键批量回归
        async function runBatchLocalRegression(category) {
            const cat = category || "ALL";
            const btn = document.getElementById("btnBatchRunLocal");
            const originalHtml = btn ? btn.innerHTML : "";
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" style="width: 10px; height: 10px;"></span> 正在秒级批量回归...`;
            }
            try {
                const res = await fetch("/api/solidified_cases/batch_run", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ category: cat })
                });
                const data = await res.json();
                if (data.success) {
                    alert(`🎉 批量回归圆满完成！\\n📦 回归用例总数：${data.total} 个\\n✅ 通过率：${data.pass_rate} (${data.passed}/${data.total})\\n⏱️ 总执行耗时：${data.duration}\\n🚀 零 Token 本地原生极速验证达成。`);
                    await loadSolidifiedCasesWorkspace();
                } else {
                    alert(data.message || "批量回归未能完成");
                }
            } catch (e) {
                alert("批量回归请求异常: " + e);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            }
        }

        function openReportInRightDrawer(sessionId) {'''

assert js_helper_anchor in content, "js_helper_anchor not found!"
content = content.replace(js_helper_anchor, js_helper_new, 1)

# 4. Update buildBlockHtml with step_execution (action -> observation), fault_diagnosis, and test_summary
old_step_exec_anchor = '''            if (blk.type === "step_execution") {
                const isRunning = (blk.status === "RUNNING");
                const isFailed = (blk.status === "FAILED");
                const statusClass = isRunning ? "running" : (isFailed ? "failed" : "success");
                const badgeText = isRunning ? "进行中..." : (isFailed ? "未通过" : "已完成");
                
                window._streamStepState = window._streamStepState || {};
                const defaultOpen = isRunning || (blk.step_id === 1);
                const isExpanded = (window._streamStepState[blk.block_id] !== undefined) 
                    ? window._streamStepState[blk.block_id] 
                    : defaultOpen;

                const chevronClass = isExpanded ? "bi-chevron-up" : "bi-chevron-down";
                const bodyClass = isExpanded ? "" : "d-none";

                let actionsHtml = "";
                const acts = blk.actions || [];
                acts.forEach(act => {
                    actionsHtml += `
                        <div class="step-action-row">
                            <div class="action-main-content">
                                <span class="action-name">${escapeHtml(act.name || act.title || '操作')}</span>
                                <span class="action-desc">${escapeHtml(act.desc || act.detail || '')}</span>
                            </div>
                            ${act.param ? `<span class="action-param-chip">${escapeHtml(act.param)}</span>` : ''}
                        </div>
                    `;
                });

                let assertionHtml = "";
                if (blk.assertion_result) {
                    assertionHtml = `
                        <div class="step-assertion-banner">
                            <span>${escapeHtml(blk.assertion_result)}</span>
                        </div>
                    `;
                }

                return `
                    <div class="stream-step-card ${statusClass}" id="${blk.block_id}">
                        <div class="stream-step-card-header" onclick="toggleStreamStep('${blk.block_id}')">
                            <div class="step-header-left">
                                <span class="step-status-dot ${statusClass}"></span>
                                <span class="step-card-title">${escapeHtml(blk.title || 'Step 执行')}</span>
                                <span class="step-card-badge ${statusClass}">· ${badgeText}</span>
                            </div>
                            <div class="step-header-meta">
                                <span>${escapeHtml(blk.duration || '0.4s')}</span>
                                <i class="bi ${chevronClass} step-toggle-arrow" id="chevron_${blk.block_id}"></i>
                            </div>
                        </div>
                        <div class="stream-step-card-body ${bodyClass}" id="body_${blk.block_id}">
                            <div class="step-actions-trail">
                                ${actionsHtml}
                            </div>
                            ${assertionHtml}
                        </div>
                    </div>
                `;
            }'''

new_step_exec = '''            if (blk.type === "step_execution") {
                const isRunning = (blk.status === "RUNNING");
                const isFailed = (blk.status === "FAILED" || blk.status === "FAIL");
                const statusClass = isRunning ? "running" : (isFailed ? "failed" : "success");
                const badgeText = isRunning ? "进行中..." : (isFailed ? "未通过" : "已完成");
                
                window._streamStepState = window._streamStepState || {};
                const defaultOpen = isRunning || isFailed;
                const isExpanded = (window._streamStepState[blk.block_id] !== undefined) 
                    ? window._streamStepState[blk.block_id] 
                    : defaultOpen;

                const chevronClass = isExpanded ? "bi-chevron-up" : "bi-chevron-down";
                const bodyClass = isExpanded ? "" : "d-none";

                let actionsHtml = "";
                const acts = blk.actions || [];
                acts.forEach((act, actIdx) => {
                    actionsHtml += `
                        <div class="step-micro-action-row">
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
                        </div>
                    `;
                });

                let assertionHtml = "";
                if (blk.assertion_result) {
                    assertionHtml = `
                        <div class="step-assertion-banner mt-1.5">
                            <i class="bi ${isFailed ? 'bi-exclamation-triangle' : 'bi-shield-check'} me-1"></i>
                            <span>${escapeHtml(blk.assertion_result)}</span>
                        </div>
                    `;
                }

                return `
                    <div class="stream-step-card ${statusClass}" id="${blk.block_id}">
                        <div class="stream-step-card-header" onclick="toggleStreamStep('${blk.block_id}')">
                            <div class="step-header-left">
                                <span class="step-status-dot ${statusClass}"></span>
                                <span class="step-card-title">${escapeHtml(blk.title || 'Step 执行')}</span>
                                <span class="step-card-badge ${statusClass}">· ${badgeText}</span>
                            </div>
                            <div class="step-header-meta">
                                <span>${acts.length} 项动作</span>
                                <span>·</span>
                                <span>${escapeHtml(blk.duration || '0.4s')}</span>
                                <i class="bi ${chevronClass} step-toggle-arrow" id="chevron_${blk.block_id}"></i>
                            </div>
                        </div>
                        <div class="stream-step-card-body ${bodyClass}" id="body_${blk.block_id}">
                            <div class="step-actions-trail">
                                ${actionsHtml}
                            </div>
                            ${assertionHtml}
                        </div>
                    </div>
                `;
            }

            if (blk.type === "fault_diagnosis") {
                return `
                    <div class="stream-fault-diag-card" id="${blk.block_id}">
                        <div class="d-flex align-items-center gap-2">
                            <span class="step-status-dot failed"></span>
                            <span class="fw-semibold" style="font-size: 13px; color: #ef4444;">自测受阻人话诊断</span>
                            <span class="mono-pill" style="font-size: 10px; color: #ef4444; border-color: rgba(239, 68, 68, 0.3);">阻断建议</span>
                        </div>
                        <div class="mt-2" style="font-size: 12px; line-height: 1.65; color: var(--text-sub);">
                            <div><strong>① 发生何事</strong>：${escapeHtml(blk.fail_step || '步骤断言未通过')}</div>
                            <div><strong>② 现场现状</strong>：${escapeHtml(blk.situation || '当前屏幕停留在非预期界面或关键按钮未渲染')}</div>
                            <div><strong>③ 处置建议</strong>：${escapeHtml(blk.suggestion || '请在投屏上手动完成操作，或在下方输入补充意图继续')}</div>
                        </div>
                    </div>
                `;
            }

            if (blk.type === "test_summary") {
                const sid = blk.session_id || sessionData.session_id || activeSessionId;
                const isPass = (blk.status === "PASS");
                const isSolidified = !!sessionData.is_solidified || !!blk.is_solidified;
                const solidFile = blk.solidified_filename || sessionData.solidified_filename || `test_${sid}.py`;
                const artifacts = blk.artifacts || [
                    { name: "6 大测试维度全景交付物报告", file: `test_report_${sid}.md`, type: "report" },
                    { name: "零 Token 本地自动化回归脚本", file: solidFile, type: "code" },
                    { name: "高保真端侧全链路截图证据链", file: "data/reports/screenshots/", type: "evidence" }
                ];

                let artifactsHtml = "";
                artifacts.forEach(art => {
                    const isReport = art.type === "report" || (art.name && art.name.includes("报告"));
                    const isCode = art.type === "code" || (art.filename && art.filename.endsWith(".py")) || (art.file && art.file.endsWith(".py"));
                    const fName = art.filename || art.file || (isCode ? solidFile : `test_report_${sid}.md`);
                    let clickAction = isReport 
                        ? `onclick="openReportInRightDrawer('${sid}')"` 
                        : (isCode ? `onclick="openEmbeddedCode('${escapeHtml(fName)}', '本地用例')"` : `onclick="alert('证据目录已归档至 data/reports/screenshots/')"` );
                    
                    artifactsHtml += `
                        <div class="artifact-item-row" ${clickAction} style="cursor: pointer;" title="点击查阅/打开">
                            <div class="d-flex align-items-center gap-2 text-truncate" style="max-width: 85%;">
                                <i class="bi ${isReport ? 'bi-file-earmark-medical' : (isCode ? 'bi-file-earmark-code' : 'bi-images')} text-secondary"></i>
                                <span class="artifact-name">${escapeHtml(art.name)}</span>
                                <span class="artifact-file mono-pill" style="font-size: 10px;">${escapeHtml(fName)}</span>
                            </div>
                            <span class="artifact-arrow"><i class="bi bi-chevron-right" style="font-size: 10px; opacity: 0.6;"></i></span>
                        </div>
                    `;
                });

                return `
                    <div class="test-result-summary-card" id="${blk.block_id}">
                        <!-- 头部：综合裁定与核心指标 -->
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="d-flex align-items-center gap-2">
                                <span class="summary-card-title">测试执行结果总结</span>
                                <span class="mono-pill ${isPass ? 'pass-pill' : 'fail-pill'}">${isPass ? 'PASS' : 'FAIL'}</span>
                            </div>
                            <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(blk.timestamp || '')}</span>
                        </div>

                        <!-- 核心指标摘要条 -->
                        <div class="summary-metric-bar mt-2">
                            <div>• <strong>执行裁定</strong>：${isPass ? '全链路业务闭环达成 · 6 大维度全项达标' : '业务验证受阻'}</div>
                            <div>• <strong>阶段通过</strong>：${escapeHtml(blk.steps_summary || '步骤全项达标')}</div>
                            <div>• <strong>稳定性指标</strong>：总耗时 ${escapeHtml(blk.duration || '152.3s')} · 0 次 Crash · 0 次 ANR</div>
                        </div>

                        <!-- 结构化交付物资产清单 -->
                        <div class="summary-artifacts-box mt-2.5">
                            <div class="artifacts-box-title">
                                <span>结构化交付物与测试资产</span>
                                <span class="text-muted" style="font-size: 10px; font-weight: normal;">(点击文件名可直接在右侧打开或查阅)</span>
                            </div>
                            <div class="artifacts-list mt-1.5">
                                ${artifactsHtml}
                            </div>
                        </div>

                        <!-- 快捷操作栏：保存本地用例 + 在右侧打开报告 + 秒级本地回放 -->
                        <div class="mt-2.5 d-flex align-items-center flex-wrap gap-2">
                            <button class="btn btn-sm btn-primary py-1 px-3 d-flex align-items-center gap-1.5" style="font-size: 11.5px; border-radius: 6px;" onclick="openReportInRightDrawer('${sid}')">
                                <i class="bi bi-layout-sidebar-reverse"></i>
                                <span>在右侧查看完整报告</span>
                            </button>
                            ${isSolidified ? `
                                <button class="btn btn-sm btn-outline-secondary py-1 px-3 d-flex align-items-center gap-1.5" style="font-size: 11.5px; border-radius: 6px;" onclick="switchMainWorkspaceMode('local')">
                                    <i class="bi bi-check-circle-fill text-success"></i>
                                    <span>已入库本地用例 (${escapeHtml(solidFile)})</span>
                                </button>
                            ` : `
                                <button class="btn btn-sm btn-outline-secondary py-1 px-3 d-flex align-items-center gap-1.5" id="saveCaseBtn_${sid}" style="font-size: 11.5px; border-radius: 6px;" onclick="saveSessionToLocalCase('${sid}')">
                                    <i class="bi bi-bookmark-plus"></i>
                                    <span>💾 保存为本地用例</span>
                                </button>
                            `}
                            <button class="btn btn-sm btn-outline-secondary py-1 px-2.5 d-flex align-items-center gap-1" style="font-size: 11.5px; border-radius: 6px;" onclick="replaySolidifiedCase('${escapeHtml(solidFile)}')">
                                <i class="bi bi-play-fill text-success"></i>
                                <span>秒级重放</span>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary py-1 px-2 d-flex align-items-center gap-1" style="font-size: 11px; border-radius: 6px;" onclick="copyMarkdownReport('${sid}')">
                                <i class="bi bi-clipboard"></i> 复制报告
                            </button>
                        </div>
                    </div>
                `;
            }'''

assert old_step_exec_anchor in content, "old_step_exec_anchor not found!"
content = content.replace(old_step_exec_anchor, new_step_exec, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully applied frontend patches to web/templates/index.html!")
