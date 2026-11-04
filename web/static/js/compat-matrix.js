        async function openCompatibilityMatrixModal(sessionId) {
            const modalEl = document.getElementById("compatibilityMatrixModal");
            const bodyEl = document.getElementById("compatibilityMatrixBody");
            if (!modalEl || !bodyEl) return;

            bodyEl.innerHTML = `<div class="text-center p-4 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>正在对齐各机型步骤快照与性能差异...</div>`;
            const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
            bsModal.show();

            try {
                const res = await fetch(`/api/sessions/${sessionId}/compatibility_matrix`);
                const matrix = await res.json();
                renderCompatibilityMatrix(matrix);
            } catch (e) {
                bodyEl.innerHTML = `<div class="p-3 text-danger text-center">加载多端兼容性对比数据失败: ${escapeHtml(e.message)}</div>`;
            }
        }

        function renderCompatibilityMatrix(matrix) {
            const bodyEl = document.getElementById("compatibilityMatrixBody");
            if (!bodyEl) return;

            const devices = matrix.devices || [];
            const steps = matrix.aligned_steps || [];
            const summary = matrix.summary || {};

            // 1. 机型概览横栏
            let devChipsHtml = "";
            devices.forEach(d => {
                const isPass = (d.status === "COMPLETED" || d.is_success);
                devChipsHtml += `
                    <div class="matrix-device-chip">
                        <i class="bi bi-phone fs-6 text-success"></i>
                        <div>
                            <div class="fw-semibold text-truncate" style="max-width: 160px; font-size: 12px; color: var(--text-main);">${escapeHtml(d.model)}</div>
                            <div class="text-muted" style="font-size: 10px;">${escapeHtml(d.device_id)} · 耗时 ${escapeHtml(d.duration)}</div>
                        </div>
                        <span class="badge ${isPass ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-danger-subtle text-danger'}" style="font-size: 9.5px;">${isPass ? '通过' : '受阻'}</span>
                    </div>
                `;
            });

            // 2. 步骤并排对比流
            let stepsRowsHtml = "";
            steps.forEach(st => {
                let snapColsHtml = "";
                const snapMap = st.device_snapshots || {};

                devices.forEach(d => {
                    const snap = snapMap[d.device_id] || {};
                    const shotUrl = snap.screenshot_url || "";
                    snapColsHtml += `
                        <div class="col-12 col-md-6 col-lg-4">
                            <div class="matrix-snapshot-card">
                                <div class="d-flex align-items-center justify-content-between mb-1.5" style="font-size: 11px;">
                                    <span class="fw-medium text-truncate" style="max-width: 120px;">${escapeHtml(d.model)}</span>
                                    <span class="badge bg-secondary-subtle text-muted" style="font-size: 9px;"><i class="bi bi-stopwatch me-0.5"></i>${snap.duration_ms || 320}ms</span>
                                </div>
                                ${shotUrl ? `
                                    <div class="position-relative overflow-hidden rounded" style="background: #000; min-height: 140px; display: flex; align-items: center; justify-content: center;">
                                        <img src="${shotUrl}" class="matrix-shot-img w-100" onclick="zoomSnapshot('${shotUrl}', 'Step ${st.step_index}: ${escapeHtml(st.title)} - ${escapeHtml(d.model)}')" onerror="this.src='/static/icons/phone_placeholder.png'; this.style.maxHeight='80px';" />
                                    </div>
                                ` : `
                                    <div class="p-3 text-muted" style="font-size: 11px; min-height: 120px; display: flex; align-items: center; justify-content: center;">暂无快照证据</div>
                                `}
                            </div>
                        </div>
                    `;
                });

                stepsRowsHtml += `
                    <div class="matrix-step-row">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <div class="d-flex align-items-center gap-2">
                                <span class="badge bg-primary-subtle text-primary border border-primary-subtle" style="font-size: 10.5px;">Step ${st.step_index}</span>
                                <span class="fw-semibold" style="font-size: 13px; color: var(--text-main);">${escapeHtml(st.title)}</span>
                                <span class="text-muted text-truncate" style="font-size: 11px;">— ${escapeHtml(st.desc)}</span>
                            </div>
                            <span class="badge bg-success-subtle text-success border border-success-subtle" style="font-size: 10px;"><i class="bi bi-check2-circle me-1"></i>${escapeHtml(st.diff_reason || '各端视觉一致')}</span>
                        </div>
                        <div class="row g-2">
                            ${snapColsHtml}
                        </div>
                    </div>
                `;
            });

            bodyEl.innerHTML = `
                <!-- 顶部机型徽章 -->
                <div class="d-flex align-items-center gap-2 mb-3 flex-wrap">
                    ${devChipsHtml}
                </div>

                <!-- 综合裁定横幅 -->
                <div class="p-2.5 mb-3 rounded border d-flex align-items-center justify-content-between" style="background: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.25) !important;">
                    <div class="d-flex align-items-center gap-2" style="font-size: 12px;">
                        <i class="bi bi-shield-check text-success fs-5"></i>
                        <span>${escapeHtml(summary.verdict || '全机型测试通过')}</span>
                    </div>
                    <span class="badge bg-success text-white" style="font-size: 10px;">一致率 ${summary.consistency_rate || '100%'}</span>
                </div>

                <!-- 步骤对齐对比流 -->
                <div>
                    ${stepsRowsHtml}
                </div>
            `;
        }

        function zoomSnapshot(url, title) {
            const modalEl = document.getElementById("snapshotZoomModal");
            const imgEl = document.getElementById("snapshotZoomImg");
            const titleEl = document.getElementById("snapshotZoomTitle");
            if (!modalEl || !imgEl) return;
            imgEl.src = url;
            if (titleEl) titleEl.textContent = title;
            const bs = bootstrap.Modal.getOrCreateInstance(modalEl);
            bs.show();
        }

        /* ==================== 多模态需求资产交互逻辑 (Antigravity 范式) ==================== */
        let currentAttachments = [];

        function triggerAttachmentSelect(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            const fileInput = document.getElementById("attachmentFileInput");
            if (fileInput) fileInput.click();
        }

        async function handleAttachmentFileInput(e) {
            const files = e.target.files;
            if (!files || files.length === 0) return;
            await uploadAndAttachFiles(Array.from(files));
            e.target.value = "";
        }

        async function uploadAndAttachFiles(fileList) {
            if (!fileList || fileList.length === 0) return;
            const tray = document.getElementById("inputAttachmentTray");
            if (tray) tray.classList.remove("d-none");

            // 0ms 乐观添加占位微胶囊
            const tempIds = [];
            fileList.forEach(file => {
                const tempId = "att_temp_" + Date.now() + "_" + Math.random().toString(36).substring(2, 6);
                tempIds.push(tempId);
                const tempPill = document.createElement("div");
                tempPill.className = "attachment-pill";
                tempPill.id = tempId;
                tempPill.innerHTML = `
                    <span class="spinner-border spinner-border-sm text-primary" style="width: 10px; height: 10px; border-width: 1.5px;"></span>
                    <span class="attachment-pill-name">${escapeHtml(file.name || '上传中...')}</span>
                `;
                if (tray) tray.appendChild(tempPill);
            });

            try {
                const formData = new FormData();
                fileList.forEach(file => formData.append("files", file));
                const res = await fetch("/api/upload", { method: "POST", body: formData });
                const data = await res.json();

                // 移除临时占位
                tempIds.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.remove();
                });

                if (data && data.success && Array.isArray(data.files)) {
                    data.files.forEach(fMeta => {
                        currentAttachments.push(fMeta);
                    });
                    renderAttachmentTray();
                } else {
                    alert((data && data.message) ? data.message : "附件上传失败");
                }
            } catch (err) {
                console.error("上传多模态需求资产异常:", err);
                tempIds.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.remove();
                });
                alert("附件上传网络连接异常，请重试");
            }
        }

        function renderAttachmentTray() {
            const tray = document.getElementById("inputAttachmentTray");
            if (!tray) return;
            if (!currentAttachments || currentAttachments.length === 0) {
                tray.innerHTML = "";
                tray.classList.add("d-none");
                return;
            }
            tray.classList.remove("d-none");
            let html = "";
            currentAttachments.forEach((att, idx) => {
                let iconOrThumb = "";
                if (att.is_image) {
                    iconOrThumb = `<img src="${att.url}" class="attachment-pill-thumb" alt="" />`;
                } else if (att.suffix === ".docx" || att.suffix === ".doc") {
                    iconOrThumb = `<i class="bi bi-file-earmark-word text-primary" style="font-size: 13px;"></i>`;
                } else if (att.suffix === ".pdf") {
                    iconOrThumb = `<i class="bi bi-file-earmark-pdf text-danger" style="font-size: 13px;"></i>`;
                } else {
                    iconOrThumb = `<i class="bi bi-file-earmark-text text-info" style="font-size: 13px;"></i>`;
                }
                const displayName = att.filename || "需求附件";
                const displaySize = att.size || "";
                let actionBtn = "";
                if (att.is_doc) {
                    actionBtn = `
                        <span class="attachment-pill-action" onclick="generateSuiteFromAttachment('${escapeHtml(att.saved_name || '')}', '${escapeHtml(displayName)}', event)" title="基于此需求文档智能提炼系统用例套件 (Suite Builder)" style="cursor: pointer; padding: 1px 6px; border-radius: 9999px; background: rgba(99, 102, 241, 0.15); color: #818cf8; font-size: 10px; font-weight: 500; margin-left: 4px;">
                            <i class="bi bi-magic me-1"></i>提炼套件
                        </span>
                    `;
                }
                html += `
                    <div class="attachment-pill" title="${escapeHtml(displayName)} (${displaySize})">
                        ${iconOrThumb}
                        <span class="attachment-pill-name">${escapeHtml(displayName)}</span>
                        <span class="attachment-pill-size">${escapeHtml(displaySize)}</span>
                        ${actionBtn}
                        <span class="attachment-pill-remove" onclick="removeAttachment(${idx}, event)" title="移除此附件">×</span>
                    </div>
                `;
            });
            tray.innerHTML = html;
        }

        function removeAttachment(idx, event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            currentAttachments.splice(idx, 1);
            renderAttachmentTray();
        }

        function clearAttachments() {
            currentAttachments = [];
            renderAttachmentTray();
        }

        function buildAttachmentsPreviewHtml(attachments) {
            if (!Array.isArray(attachments) || attachments.length === 0) return "";
            let itemsHtml = "";
            attachments.forEach(att => {
                const displayName = att.filename || "需求附件";
                const displaySize = att.size || "";
                if (att.is_image) {
                    itemsHtml += `
                        <div class="stream-attachment-image-card" onclick="zoomSnapshot('${att.url}', '${escapeHtml(displayName)}')" title="点击全屏放大预览截图">
                            <img src="${att.url}" class="stream-attachment-img" alt="${escapeHtml(displayName)}" />
                            <span class="stream-attachment-img-badge">${escapeHtml(displaySize || 'IMG')}</span>
                        </div>
                    `;
                } else {
                    let iconClass = "bi-file-earmark-text text-info";
                    if (att.suffix === ".docx" || att.suffix === ".doc") iconClass = "bi-file-earmark-word text-primary";
                    else if (att.suffix === ".pdf") iconClass = "bi-file-earmark-pdf text-danger";

                    itemsHtml += `
                        <a href="${att.url}" target="_blank" class="stream-attachment-card" title="查看/下载附件 ${escapeHtml(displayName)}">
                            <i class="bi ${iconClass}" style="font-size: 14px;"></i>
                            <span class="stream-attachment-name" style="max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(displayName)}</span>
                            <span class="text-sub font-mono" style="font-size: 10px; opacity: 0.85;">${escapeHtml(displaySize)}</span>
                            <i class="bi bi-box-arrow-up-right ms-1 text-sub" style="font-size: 10px;"></i>
                        </a>
                    `;
                }
            });
            return `<div class="stream-attachments-wrap">${itemsHtml}</div>`;
        }

        // 初始化多模态事件监听 (Ctrl+V 粘贴截图 / 拖拽释放文档)
        document.addEventListener("DOMContentLoaded", function() {
            const taskInputEl = document.getElementById("taskInputText");
            if (taskInputEl) {
                taskInputEl.addEventListener("paste", async function(e) {
                    const clipboard = e.clipboardData;
                    if (!clipboard || !clipboard.items) return;
                    const imageFiles = [];
                    for (let i = 0; i < clipboard.items.length; i++) {
                        const item = clipboard.items[i];
                        if (item.type && item.type.indexOf("image") !== -1) {
                            const blob = item.getAsFile();
                            if (blob) {
                                const filename = `paste_img_${Date.now()}_${i+1}.png`;
                                const file = new File([blob], filename, { type: blob.type || "image/png" });
                                imageFiles.push(file);
                            }
                        }
                    }
                    if (imageFiles.length > 0) {
                        e.preventDefault();
                        await uploadAndAttachFiles(imageFiles);
                    }
                });
            }

            const gptBoxEl = document.getElementById("gptInputBox");
            if (gptBoxEl) {
                gptBoxEl.addEventListener("dragover", function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    gptBoxEl.classList.add("drag-over");
                });
                gptBoxEl.addEventListener("dragleave", function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    gptBoxEl.classList.remove("drag-over");
                });
                gptBoxEl.addEventListener("drop", async function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    gptBoxEl.classList.remove("drag-over");
                    const dt = e.dataTransfer;
                    if (dt && dt.files && dt.files.length > 0) {
                        await uploadAndAttachFiles(Array.from(dt.files));
                    }
                });
            }
        });

                // ================= 需求规约业务契合度门禁卡片 (Doc-App Relevance Guard UI) =================

        function renderDocMismatchGuardHtml(blk, sessionData) {
            const blockId = blk.block_id || ("guard_" + (sessionData ? sessionData.session_id : Date.now()));
            const docName = escapeHtml(blk.doc_name || "上传文档");
            const appName = escapeHtml(blk.app_name || (sessionData ? (sessionData.app_label || sessionData.app_id || "待测应用") : "待测应用"));
            const relInfo = blk.relevance_info || {};
            const appDomain = escapeHtml(relInfo.app_domain || "未知业务领域");
            const docDomain = escapeHtml(relInfo.doc_domain || "外部其他领域");
            const score = relInfo.relevance_score || 15;
            const reason = escapeHtml(relInfo.reason || `当前待测应用归属于「${appDomain}」，而上传的需求文档内容涉及「${docDomain}」，两者业务场景无交集。`);
            const sessionId = sessionData ? sessionData.session_id : (window.currentSessionId || "");

            return `
                <div class="stream-system-notice-row my-3" id="${blockId}">
                    <div class="doc-mismatch-card">
                        <div class="mismatch-header">
                            <span class="mismatch-tag">
                                <i class="bi bi-shield-exclamation"></i> 规约与应用业务领域不匹配拦截
                            </span>
                            <span class="mismatch-score-pill">业务契合度：<strong style="color: #ef4444;">${score}%</strong></span>
                        </div>
                        <div class="mismatch-body">
                            ${reason}
                        </div>
                        <div class="mismatch-comparison-grid">
                            <div class="mismatch-col">
                                <div class="mismatch-col-label"><i class="bi bi-file-earmark-text text-primary"></i> 上传文档业务画像</div>
                                <div class="mismatch-col-val">${docName}</div>
                                <div class="mismatch-col-sub">业务域：<strong>${docDomain}</strong></div>
                            </div>
                            <div class="mismatch-col">
                                <div class="mismatch-col-label"><i class="bi bi-app-indicator text-warning"></i> 当前选定待测应用</div>
                                <div class="mismatch-col-val">${appName}</div>
                                <div class="mismatch-col-sub">业务域：<strong>${appDomain}</strong></div>
                            </div>
                        </div>
                        <div class="mismatch-actions">
                            <button class="btn-mismatch-action btn-mismatch-switch" onclick="focusAppSelector()" title="切换至与文档匹配的应用">
                                <i class="bi bi-arrow-repeat"></i> 更换待测应用
                            </button>
                            <button class="btn-mismatch-action btn-mismatch-switch" onclick="focusChatUpload()" title="重新上传该应用对应的业务说明书">
                                <i class="bi bi-upload"></i> 重新上传文档
                            </button>
                            <button class="btn-mismatch-action btn-mismatch-force" onclick="forceRunDocSuite('${sessionId}')" title="忽略警告，仍以此文档提炼用例并驱动当前应用测试">
                                <i class="bi bi-play-circle"></i> 仍要强行测试
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        function focusAppSelector() {
            const el = document.getElementById("appSelect") || document.querySelector(".app-selector");
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "center" });
                el.focus();
            }
            if (typeof showToast === "function") {
                showToast("请在顶部应用选择区切换至对应应用后重新提交");
            }
        }

        function focusChatUpload() {
            const input = document.getElementById("fileInput");
            if (input) {
                input.click();
            } else if (typeof showToast === "function") {
                showToast("请在底部对话框重新上传与目标应用相关的测试文档");
            }
        }

        async function forceRunDocSuite(sessionId) {
            if (!sessionId) {
                sessionId = window.currentSessionId;
            }
            if (!sessionId) {
                if (typeof showToast === "function") showToast("无法获取当前会话 ID", "error");
                return;
            }
            try {
                const resp = await fetch(`/api/sessions/${sessionId}/force_run_doc_suite`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" }
                });
                const res = await resp.json();
                if (res.success) {
                    if (typeof showToast === "function") showToast("已强制放行，正在为您提炼用例并驱动真机测试...", "success");
                    if (typeof fetchSessionDetails === "function") {
                        fetchSessionDetails(sessionId);
                    }
                } else {
                    if (typeof showToast === "function") showToast(res.message || "操作失败", "error");
                }
            } catch (e) {
                console.error("forceRunDocSuite error:", e);
                if (typeof showToast === "function") showToast("网络请求异常，请稍后重试", "error");
            }
        }

        // ================= 需求驱动用例编排套件 (Suite Builder Generative UI) =================

        function renderSuiteBuilderHtml(suiteData, cardId) {
            const cId = cardId || ("suite_builder_" + Date.now() + "_" + Math.random().toString(36).substring(2, 6));
            const suiteTitle = escapeHtml(suiteData.suite_title || "需求驱动系统测试用例编排套件");
            const docName = escapeHtml(suiteData.doc_filename || "需求规格说明书");
            const cases = Array.isArray(suiteData.cases) ? suiteData.cases : [];
            const keepState = suiteData.keep_state !== false;

            let rowsHtml = "";
            cases.forEach((c, idx) => {
                const caseId = escapeHtml(c.id || `tc-${idx+1}`);
                const isChecked = c.checked !== false;
                const prio = (c.priority || "P1").toUpperCase();
                let prioClass = "priority-p1";
                if (prio === "P0") prioClass = "priority-p0";
                else if (prio === "P2") prioClass = "priority-p2";

                const depHtml = c.depends_on ? `<span class="case-dep-tag" title="执行前无需重启，直接继承上一条现场状态"><i class="bi bi-link-45deg"></i> ${escapeHtml(c.depends_on)}</span>` : "";

                rowsHtml += `
                    <div class="suite-case-row ${isChecked ? '' : 'disabled'}" data-id="${caseId}" data-assert="${escapeHtml(c.assert_rule || '')}" draggable="true">
                        <span class="case-handle" title="按住拖拽排序"><i class="bi bi-grip-vertical"></i></span>
                        <input type="checkbox" class="case-select-checkbox" ${isChecked ? 'checked' : ''} onchange="updateSuiteCardSummary(this)">
                        <div class="case-content">
                            <div class="case-main-line">
                                <span class="case-priority-badge ${prioClass}">${escapeHtml(prio)}</span>
                                <span class="case-module-tag">${escapeHtml(c.module || '业务模块')}</span>
                                <span class="editable-field" contenteditable="true" spellcheck="false" title="点击可直接编辑用例标题">${escapeHtml(c.title || '')}</span>
                            </div>
                            <div class="case-sub-line">
                                <span class="case-goal-text" contenteditable="true" spellcheck="false" title="点击微调业务目标与入参">${escapeHtml(c.goal || '')}</span>
                                <span class="case-assert-tag" title="点击微调断言验证规则"><i class="bi bi-shield-check text-success" style="font-size: 11px;"></i><span class="case-assert-text" contenteditable="true" spellcheck="false" title="点击编辑断言规则">${escapeHtml(c.assert_rule || '断言页面状态正常且关键元素可见')}</span></span>
                                ${depHtml}
                            </div>
                        </div>
                        <div class="case-actions">
                            <button class="case-action-btn" title="上移" onclick="moveSuiteRow(this, -1)"><i class="bi bi-arrow-up"></i></button>
                            <button class="case-action-btn" title="下移" onclick="moveSuiteRow(this, 1)"><i class="bi bi-arrow-down"></i></button>
                            <button class="case-action-btn btn-delete" title="移除此项" onclick="deleteSuiteRow(this)"><i class="bi bi-trash3"></i></button>
                        </div>
                    </div>
                `;
            });

            const checkedCount = cases.filter(c => c.checked !== false).length;
            const estMinutes = (checkedCount * 0.45).toFixed(1);

            return `
                <div class="suite-builder-card" id="${cId}" data-doc="${docName}">
                    <div class="suite-header">
                        <div class="suite-meta-left">
                            <span class="suite-doc-badge">
                                <i class="bi bi-file-earmark-text"></i> ${docName}
                            </span>
                            <span class="suite-title-text">${suiteTitle}</span>
                        </div>
                        <div class="suite-toggles-right">
                            <label class="clean-switch" title="上一项用例执行成功后，保持应用现场不重启，直接串联执行下一项">
                                <input type="checkbox" class="suite-keep-context" ${keepState ? 'checked' : ''}>
                                <span>保持现场串联执行</span>
                            </label>
                        </div>
                    </div>
                    <div class="suite-case-list">
                        ${rowsHtml}
                    </div>
                    <div class="suite-footer">
                        <div class="footer-left">
                            <button class="btn-add-case" onclick="addNewSuiteCustomRow(this)">
                                <i class="bi bi-plus-lg"></i> 添加自定义用例
                            </button>
                            <span class="footer-summary">已选择 ${checkedCount} / ${cases.length} 项用例 (预计执行 ${estMinutes} 分钟)</span>
                        </div>
                        <div class="footer-right">
                            <button class="btn-secondary-action" onclick="saveCardAsSuite(this)" title="固化到项目用例库中，随时一键复跑">
                                <i class="bi bi-bookmark-check me-1"></i> 保存为套件
                            </button>
                            <button class="btn-primary-run" onclick="triggerCardSystemicRun(this)">
                                <i class="bi bi-play-fill" style="font-size: 13px;"></i> 执行选中的系统测试
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        function initSuiteCardDragAndDrop(card) {
            const list = card.querySelector(".suite-case-list");
            if (!list || list._dndInit) return;
            list._dndInit = true;

            let draggedItem = null;

            list.addEventListener("dragstart", function(e) {
                const row = e.target.closest(".suite-case-row");
                if (!row) return;
                if (e.target.isContentEditable || e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") {
                    e.preventDefault();
                    return;
                }
                draggedItem = row;
                row.classList.add("dragging");
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", row.getAttribute("data-id") || "");
            });

            list.addEventListener("dragend", function(e) {
                if (draggedItem) {
                    draggedItem.classList.remove("dragging");
                    draggedItem = null;
                }
                list.querySelectorAll(".suite-case-row").forEach(r => r.classList.remove("drag-over"));
                updateSuiteCardSummary(card);
            });

            list.addEventListener("dragover", function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                const targetRow = e.target.closest(".suite-case-row");
                if (targetRow && targetRow !== draggedItem) {
                    const rect = targetRow.getBoundingClientRect();
                    const next = (e.clientY - rect.top) / (rect.bottom - rect.top) > 0.5;
                    list.insertBefore(draggedItem, next ? targetRow.nextSibling : targetRow);
                }
            });
        }

        function renderSuiteBuilderCard(suiteData, containerId) {
            const html = renderSuiteBuilderHtml(suiteData);
            let targetEl = containerId ? document.getElementById(containerId) : null;
            if (!targetEl) {
                targetEl = document.getElementById("streamFlow") || document.getElementById("timelineList");
            }
            if (targetEl) {
                targetEl.insertAdjacentHTML("beforeend", html);
                const lastCard = targetEl.querySelector(".suite-builder-card:last-child");
                if (lastCard) initSuiteCardDragAndDrop(lastCard);
                targetEl.scrollTop = targetEl.scrollHeight;
            }
            return html;
        }

        function updateSuiteCardSummary(el) {
            const card = (el && el.classList && el.classList.contains("suite-builder-card")) ? el : (el ? el.closest(".suite-builder-card") : null);
            if (!card) return;
            const rows = card.querySelectorAll(".suite-case-row");
            let total = rows.length;
            let checked = 0;
            rows.forEach(r => {
                const cb = r.querySelector(".case-select-checkbox");
                if (cb && cb.checked) {
                    checked++;
                    r.classList.remove("disabled");
                } else {
                    r.classList.add("disabled");
                }
            });
            const summary = card.querySelector(".footer-summary");
            if (summary) {
                const estMin = (checked * 0.45).toFixed(1);
                summary.innerText = `已选择 ${checked} / ${total} 项用例 (预计执行 ${estMin} 分钟)`;
            }
        }

        function moveSuiteRow(btn, dir) {
            const row = btn.closest(".suite-case-row");
            if (!row) return;
            const card = btn.closest(".suite-builder-card");
            if (dir === -1 && row.previousElementSibling) {
                row.parentNode.insertBefore(row, row.previousElementSibling);
            } else if (dir === 1 && row.nextElementSibling) {
                row.parentNode.insertBefore(row.nextElementSibling, row);
            }
            if (card) updateSuiteCardSummary(card);
        }

        function deleteSuiteRow(btn) {
            const row = btn.closest(".suite-case-row");
            if (!row) return;
            const card = btn.closest(".suite-builder-card");
            row.style.opacity = '0';
            row.style.transform = 'translateX(10px)';
            row.style.transition = 'all 0.15s ease';
            setTimeout(() => {
                row.remove();
                if (card) updateSuiteCardSummary(card);
            }, 150);
        }

        function addNewSuiteCustomRow(btn) {
            const card = btn.closest(".suite-builder-card");
            if (!card) return;
            const list = card.querySelector(".suite-case-list");
            const newRow = document.createElement("div");
            newRow.className = "suite-case-row";
            newRow.setAttribute("draggable", "true");
            newRow.setAttribute("data-id", `tc-${Date.now().toString(36).substring(4)}`);
            newRow.setAttribute("data-assert", "断言页面状态正常且关键元素可见");
            newRow.innerHTML = `
                <span class="case-handle" title="按住拖拽排序"><i class="bi bi-grip-vertical"></i></span>
                <input type="checkbox" class="case-select-checkbox" checked onchange="updateSuiteCardSummary(this)">
                <div class="case-content">
                    <div class="case-main-line">
                        <span class="case-priority-badge priority-p1">P1</span>
                        <span class="case-module-tag">自定义模块</span>
                        <span class="editable-field" contenteditable="true" spellcheck="false">新测试用例标题（点击编辑）</span>
                    </div>
                    <div class="case-sub-line">
                        <span class="case-goal-text" contenteditable="true" spellcheck="false">输入具体测试目标与交互步骤...</span>
                        <span class="case-assert-tag" title="点击微调断言验证规则"><i class="bi bi-shield-check text-success" style="font-size: 11px;"></i><span class="case-assert-text" contenteditable="true" spellcheck="false">断言页面状态正常且关键元素可见</span></span>
                    </div>
                </div>
                <div class="case-actions">
                    <button class="case-action-btn" title="上移" onclick="moveSuiteRow(this, -1)"><i class="bi bi-arrow-up"></i></button>
                    <button class="case-action-btn" title="下移" onclick="moveSuiteRow(this, 1)"><i class="bi bi-arrow-down"></i></button>
                    <button class="case-action-btn btn-delete" title="移除此项" onclick="deleteSuiteRow(this)"><i class="bi bi-trash3"></i></button>
                </div>
            `;
            list.appendChild(newRow);
            initSuiteCardDragAndDrop(card);
            updateSuiteCardSummary(card);
            const editEl = newRow.querySelector(".editable-field");
            if (editEl) editEl.focus();
        }

        function collectSuiteCardData(cardEl) {
            const titleEl = cardEl.querySelector(".suite-title-text");
            const suiteTitle = titleEl ? titleEl.innerText.trim() : "系统测试套件";
            const docName = cardEl.getAttribute("data-doc") || "";
            const keepCtxEl = cardEl.querySelector(".suite-keep-context");
            const keepState = keepCtxEl ? keepCtxEl.checked : true;

            const cases = [];
            const rows = cardEl.querySelectorAll(".suite-case-row");
            rows.forEach((r, idx) => {
                const cb = r.querySelector(".case-select-checkbox");
                const isChecked = cb ? cb.checked : true;
                const prioEl = r.querySelector(".case-priority-badge");
                const prio = prioEl ? prioEl.innerText.trim() : "P1";
                const modEl = r.querySelector(".case-module-tag");
                const mod = modEl ? modEl.innerText.trim() : "业务模块";
                const titleField = r.querySelector(".editable-field");
                const caseTitle = titleField ? titleField.innerText.trim() : `用例 ${idx+1}`;
                const goalField = r.querySelector(".case-goal-text");
                const caseGoal = goalField ? goalField.innerText.trim() : caseTitle;
                const assertField = r.querySelector(".case-assert-text");
                const caseAssert = assertField ? assertField.innerText.trim() : (r.getAttribute("data-assert") || "断言页面状态正常且关键元素可见");
                const depEl = r.querySelector(".case-dep-tag");
                const dependsOn = depEl ? depEl.innerText.replace(/[\\n\\r]+/g, '').trim() : "";

                cases.push({
                    id: r.getAttribute("data-id") || `tc-${idx+1}`,
                    title: caseTitle,
                    module: mod,
                    priority: prio,
                    goal: caseGoal,
                    assert_rule: caseAssert,
                    depends_on: dependsOn,
                    checked: isChecked
                });
            });

            return {
                suite_title: suiteTitle,
                doc_filename: docName,
                keep_state: keepState,
                cases: cases
            };
        }

        async function saveCardAsSuite(btn) {
            const card = btn.closest(".suite-builder-card");
            if (!card) return;
            const suiteData = collectSuiteCardData(card);
            const origHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" style="width:10px;height:10px;"></span> 正在存盘...`;

            try {
                const res = await fetch("/api/test_suite/save", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({suite_data: suiteData})
                });
                const data = await res.json();
                if (data && data.success) {
                    btn.innerHTML = `<i class="bi bi-check-lg text-success me-1"></i> 已保存至用例库`;
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.innerHTML = origHtml;
                    }, 2500);
                } else {
                    alert((data && data.message) ? data.message : "保存套件失败");
                    btn.disabled = false;
                    btn.innerHTML = origHtml;
                }
            } catch (err) {
                alert("保存套件网络异常: " + err.message);
                btn.disabled = false;
                btn.innerHTML = origHtml;
            }
        }

        async function triggerCardSystemicRun(btn) {
            const card = btn.closest(".suite-builder-card");
            if (!card) return;
            const suiteData = collectSuiteCardData(card);
            const checkedCases = suiteData.cases.filter(c => c.checked);
            if (checkedCases.length === 0) {
                alert("请至少勾选 1 项测试用例后再执行！");
                return;
            }

            const origHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" style="width:11px;height:11px;"></span> 正在调度真机...`;

            try {
                const devId = (typeof getPipTargetDeviceId === 'function' ? getPipTargetDeviceId() : null) || 'auto';
                const res = await fetch("/api/test_suite/run", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        session_id: window.currentSessionId || null,
                        suite_data: {
                            suite_title: suiteData.suite_title,
                            doc_filename: suiteData.doc_filename,
                            keep_state: suiteData.keep_state,
                            cases: checkedCases,
                            device_ids: devId ? [devId] : []
                        },
                        keep_state: suiteData.keep_state
                    })
                });
                const data = await res.json();
                if (data && data.success) {
                    btn.innerHTML = `🚀 系统级测试已启动`;
                    if (data.session_id) {
                        window.currentSessionId = data.session_id;
                        if (typeof pollCurrentSession === "function") {
                            await pollCurrentSession();
                        }
                    }
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.innerHTML = origHtml;
                    }, 3000);
                } else {
                    alert((data && data.message) ? data.message : "执行系统测试失败");
                    btn.disabled = false;
                    btn.innerHTML = origHtml;
                }
            } catch (err) {
                alert("执行系统测试网络异常: " + err.message);
                btn.disabled = false;
                btn.innerHTML = origHtml;
            }
        }

        let isGeneratingSuite = false;
        async function generateSuiteFromAttachment(savedFilename, origFilename, event) {
            if (isGeneratingSuite) return;
            isGeneratingSuite = true;
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            const flow = document.getElementById("streamFlow") || document.getElementById("timelineList");
            const tempPromptId = "temp_suite_prompt_" + Date.now();
            if (flow) {
                flow.insertAdjacentHTML("beforeend", `
                    <div class="stream-user-row" id="${tempPromptId}">
                        <div class="stream-user-prompt">
                            <div class="stream-user-prompt-meta">
                                <i class="bi bi-file-earmark-text"></i>
                                <span>需求文档驱动提炼</span>
                            </div>
                            <div class="stream-user-prompt-content">
                                请阅读需求文档《${escapeHtml(origFilename)}》，智能提炼端到端系统测试用例套件并启动编排。
                            </div>
                        </div>
                    </div>
                    <div class="stream-thought-box" id="loading_${tempPromptId}">
                        <div class="stream-thought-pill">
                            <span class="thought-pulse-dot pulsing"></span>
                            <span class="fw-medium font-mono" style="font-size: 11px;">Suite Synthesizer Thinking...</span>
                        </div>
                        <div class="stream-thought-drawer">
                            <div class="d-flex align-items-center gap-2" style="font-size: 11.5px; color: var(--text-sub);">
                                <span class="spinner-border spinner-border-sm text-primary" style="width: 10px; height: 10px; border-width: 1.5px;"></span>
                                <span>大模型正在语义解析需求规格说明书，构建多模块测试用例与状态现场串联图谱...</span>
                            </div>
                        </div>
                    </div>
                `);
                flow.scrollTop = flow.scrollHeight;
            }

            try {
                const res = await fetch("/api/test_suite/synthesize", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        filename: savedFilename,
                        doc_filename: origFilename,
                        provider: (typeof currentActiveProvider !== 'undefined' ? currentActiveProvider : null),
                        model: (typeof currentActiveModel !== 'undefined' ? currentActiveModel : null)
                    })
                });
                const data = await res.json();
                const loadEl = document.getElementById("loading_" + tempPromptId);
                if (loadEl) loadEl.remove();

                if (data && data.success && data.suite) {
                    renderSuiteBuilderCard(data.suite);
                } else {
                    alert((data && data.message) ? data.message : "提炼套件失败");
                }
            } catch (err) {
                const loadEl = document.getElementById("loading_" + tempPromptId);
                if (loadEl) loadEl.remove();
                alert("智能提炼用例套件网络连接异常: " + err.message);
            } finally {
                isGeneratingSuite = false;
            }
        }
    
