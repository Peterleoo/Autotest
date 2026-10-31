/**
 * 聊天框图片/需求文档 -> AI 拆解测试用例（可再次编辑）
 *
 * 该模块以独立脚本挂载到新版界面，避免侵入 Suite Builder 与感知/执行链路：
 * - 在输入框工具栏新增“拆解用例”入口
 * - 支持拖拽图片/文档到聊天框直接解析
 * - 生成结果展示在推荐用例区与弹窗中，每条用例均可再次编辑
 */
(function () {
    "use strict";

    const CHAT_ATTACHMENT_EXTS = [
        ".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".xlsx", ".xls",
        ".png", ".jpg", ".jpeg", ".webp", ".bmp"
    ];
    const MAX_FILES = 5;
    const MAX_FILE_SIZE = 20 * 1024 * 1024;

    let pendingChatAttachments = [];
    let chatAttachmentBusy = false;
    let generatedCases = [];
    let generatedCasesAppLabel = "待测应用";
    let editingCaseIndex = -1;

    function escapeHtml(str) {
        if (typeof window.escapeHtml === "function") return window.escapeHtml(str);
        return String(str == null ? "" : str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function isImageFile(name) {
        return /\.(png|jpe?g|webp|bmp|gif)$/i.test(name || "");
    }

    function getActiveAppLabel() {
        try {
            if (typeof currentActiveApp !== "undefined" && currentActiveApp) {
                return currentActiveApp.label || currentActiveApp.filename || "待测应用";
            }
        } catch (e) {}
        return "待测应用";
    }

    function injectStyles() {
        if (document.getElementById("chatCaseGenStyles")) return;
        const style = document.createElement("style");
        style.id = "chatCaseGenStyles";
        style.textContent = `
            .chat-case-edit-btn {
                display: inline-flex;
                align-items: center;
                gap: 3px;
                padding: 1px 7px;
                border-radius: 9999px;
                border: 1px solid var(--border-subtle);
                background: transparent;
                color: var(--text-sub);
                font-size: 10px;
                line-height: 1.5;
                cursor: pointer;
                flex-shrink: 0;
                transition: all 0.15s ease;
            }
            .chat-case-edit-btn:hover {
                color: #6366f1;
                border-color: rgba(99, 102, 241, 0.5);
                background: rgba(99, 102, 241, 0.08);
            }
            #generatedCaseEditModal .form-control,
            #generatedCaseEditModal .form-select {
                background: var(--bg-main);
                border: 1px solid var(--border-strong);
                color: var(--text-main);
                font-size: 12px;
                border-radius: 7px;
            }
            #generatedCaseEditModal .form-control:focus,
            #generatedCaseEditModal .form-select:focus {
                border-color: #6366f1;
                box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.18);
                background: var(--bg-main);
                color: var(--text-main);
            }
            #generatedCaseEditModal .form-label {
                font-size: 10.5px;
                color: var(--text-sub);
                margin-bottom: 3px;
            }
            .chat-case-hint {
                grid-column: 1 / -1;
                font-size: 10.5px;
                color: var(--text-sub);
                padding: 0 2px 2px;
            }
        `;
        document.head.appendChild(style);
    }

    function injectUi() {
        // 工具栏“拆解用例”入口（保留原有别针附件与 Suite Builder 不变）
        if (!document.getElementById("btnChatCaseGen")) {
            const anchor = document.getElementById("attachmentFileInput");
            if (anchor) {
                anchor.insertAdjacentHTML("afterend", `
                    <button class="pill-btn" type="button" id="btnChatCaseGen"
                            title="上传图片或需求文档，由模型拆解为多条可编辑测试用例">
                        <i class="bi bi-stars" style="font-size: 12px;"></i>
                        <span>拆解用例</span>
                    </button>
                    <input type="file" id="chatAttachmentInput" class="d-none" multiple
                           accept=".pdf,.docx,.txt,.md,.markdown,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.webp,.bmp"
                           onchange="handleChatAttachmentSelect(event)">
                `);
            }
        }

        // 附件状态条（放在原有附件托盘下方）
        if (!document.getElementById("chatAttachmentStrip")) {
            const tray = document.getElementById("inputAttachmentTray");
            if (tray) {
                tray.insertAdjacentHTML("afterend", `
                    <div id="chatAttachmentStrip" class="chat-attachment-strip" style="display:none;">
                        <div class="d-flex align-items-center justify-content-between gap-2">
                            <div id="chatAttachmentChips" class="d-flex flex-wrap gap-1"></div>
                            <button class="btn btn-sm btn-link p-0 text-muted text-decoration-none" style="font-size:10.5px;"
                                    onclick="clearChatAttachments()" title="清空附件">清空</button>
                        </div>
                        <div id="chatAttachmentStatus" class="chat-attachment-status"></div>
                    </div>
                `);
            }
        }

        // 用例编辑弹窗
        if (!document.getElementById("generatedCaseEditModal")) {
            document.body.insertAdjacentHTML("beforeend", `
                <div class="modal fade" id="generatedCaseEditModal" tabindex="-1" aria-hidden="true">
                    <div class="modal-dialog modal-dialog-centered">
                        <div class="modal-content" style="background: var(--bg-surface); border: 1px solid var(--border-strong); border-radius: 14px;">
                            <div class="modal-header pb-2 pt-3 px-3" style="border-bottom: 1px solid var(--border-subtle);">
                                <div class="d-flex align-items-center gap-2">
                                    <i class="bi bi-pencil-square text-primary"></i>
                                    <span class="modal-title fw-semibold" style="font-size: 13px;">编辑测试用例</span>
                                    <span class="badge bg-secondary-subtle text-secondary" id="genCaseEditBadge" style="font-size: 9.5px;">DOC-01</span>
                                    <span class="text-muted" style="font-size: 10px;">修改后再次点击编辑可继续调整</span>
                                </div>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body p-3">
                                <div class="row g-2">
                                    <div class="col-8">
                                        <label class="form-label">用例标题</label>
                                        <input id="genCaseEditTitle" class="form-control form-control-sm" maxlength="120" placeholder="请输入用例标题">
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label">优先级</label>
                                        <select id="genCaseEditLevel" class="form-select form-select-sm">
                                            <option value="P0">P0 · 核心</option>
                                            <option value="P1">P1 · 重要</option>
                                            <option value="P2">P2 · 一般</option>
                                        </select>
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label">所属模块</label>
                                        <input id="genCaseEditModule" class="form-control form-control-sm" maxlength="60" placeholder="例如：二手房列表">
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label">测试目标与操作步骤</label>
                                        <textarea id="genCaseEditGoal" class="form-control" rows="4" placeholder="描述进入路径、操作步骤与预期断言"></textarea>
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label">用例说明</label>
                                        <textarea id="genCaseEditDesc" class="form-control" rows="2" placeholder="可选：补充用例说明"></textarea>
                                    </div>
                                    <div class="col-12">
                                        <label class="form-label">前置条件</label>
                                        <textarea id="genCaseEditPrecondition" class="form-control" rows="2" placeholder="可选：例如已登录、已安装应用"></textarea>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer border-top d-flex justify-content-between" style="border-color: var(--border-subtle) !important;">
                                <button type="button" class="btn btn-sm btn-outline-secondary px-3" data-bs-dismiss="modal">取消</button>
                                <button type="button" class="btn btn-sm btn-primary px-4 fw-semibold" onclick="saveGeneratedCaseEdit()">
                                    <i class="bi bi-check2 me-1"></i>保存修改
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `);
        }
    }

    function triggerChatAttachment() {
        const input = document.getElementById("chatAttachmentInput");
        if (input) input.click();
    }

    function handleChatAttachmentSelect(event) {
        const files = Array.from(event.target.files || []);
        event.target.value = "";
        if (files.length) addChatAttachments(files);
    }

    function addChatAttachments(files) {
        if (chatAttachmentBusy) {
            alert("正在解析上一批附件，请稍候...");
            return;
        }
        const accepted = [];
        for (const file of files) {
            const dot = file.name.lastIndexOf(".");
            const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
            if (!CHAT_ATTACHMENT_EXTS.includes(ext)) {
                alert(`仅支持图片和需求文档（PDF/DOCX/TXT/MD/CSV/XLSX/图片）：\n${file.name}\nAPK 请通过“应用管理”上传。`);
                continue;
            }
            if (file.size > MAX_FILE_SIZE) {
                alert(`附件超过 20MB 限制：${file.name}`);
                continue;
            }
            accepted.push(file);
        }
        if (!accepted.length) return;
        pendingChatAttachments = accepted.slice(0, MAX_FILES);
        renderChatAttachmentChips();
        const status = document.getElementById("chatAttachmentStatus");
        if (status) status.innerText = `已添加 ${pendingChatAttachments.length} 个附件，正在调用模型拆解用例...`;
        generateChatCasesFromAttachments();
    }

    function renderChatAttachmentChips() {
        const strip = document.getElementById("chatAttachmentStrip");
        const box = document.getElementById("chatAttachmentChips");
        if (!strip || !box) return;
        strip.style.display = pendingChatAttachments.length ? "flex" : "none";
        box.innerHTML = pendingChatAttachments.map((file, idx) => `
            <span class="chat-attachment-chip" title="${escapeHtml(file.name)}">
                <i class="bi ${isImageFile(file.name) ? "bi-image" : "bi-file-earmark-text"}"></i>
                <span class="text-truncate">${escapeHtml(file.name)}</span>
                <span class="remove" onclick="removeChatAttachment(${idx})" title="移除">&times;</span>
            </span>`).join("");
    }

    function removeChatAttachment(idx) {
        if (chatAttachmentBusy) return;
        pendingChatAttachments.splice(idx, 1);
        renderChatAttachmentChips();
        if (!pendingChatAttachments.length) {
            const status = document.getElementById("chatAttachmentStatus");
            if (status) status.innerText = "";
        }
    }

    function clearChatAttachments() {
        if (chatAttachmentBusy) return;
        pendingChatAttachments = [];
        renderChatAttachmentChips();
        const status = document.getElementById("chatAttachmentStatus");
        if (status) status.innerText = "";
    }

    async function generateChatCasesFromAttachments() {
        if (chatAttachmentBusy || !pendingChatAttachments.length) return;
        chatAttachmentBusy = true;
        const status = document.getElementById("chatAttachmentStatus");
        if (status) status.innerHTML = `<span class="spinner-border spinner-border-sm me-1" style="width:10px;height:10px;"></span>正在提取附件内容并调用模型拆解测试用例...`;

        const fd = new FormData();
        pendingChatAttachments.forEach(file => fd.append("files", file, file.name));
        const appLabel = getActiveAppLabel();
        fd.append("app_name", appLabel);
        fd.append("instruction", (document.getElementById("taskInputText")?.value || "").trim());
        try {
            if (typeof currentActiveProvider !== "undefined" && currentActiveProvider) fd.append("provider", currentActiveProvider);
            if (typeof currentActiveModel !== "undefined" && currentActiveModel) fd.append("model", currentActiveModel);
        } catch (e) {}

        try {
            const res = await fetch("/api/ai/generate_cases_from_files", { method: "POST", body: fd });
            let data = {};
            try { data = await res.json(); } catch (e) { throw new Error(`HTTP ${res.status}`); }
            if (!res.ok || !data.success) {
                throw new Error(data.message || data.detail || `HTTP ${res.status}`);
            }
            const cases = data.cases || [];
            if (!cases.length) throw new Error("模型未返回有效测试用例");
            generatedCases = cases.map(c => ({ ...c }));
            generatedCasesAppLabel = appLabel;
            renderGeneratedCases(generatedCases, appLabel, true);
            const fileCount = (data.files || pendingChatAttachments).length;
            if (status) {
                status.innerHTML = `<span class="text-success"><i class="bi bi-check-circle me-1"></i>已解析 ${fileCount} 个附件，生成 ${cases.length} 条用例；点击卡片填入输入框，点击 ✏️ 可再次编辑</span>`;
            }
        } catch (e) {
            if (status) {
                status.innerHTML = `<span class="text-danger"><i class="bi bi-exclamation-triangle me-1"></i>${escapeHtml(e.message || String(e))}</span>`;
            }
        } finally {
            chatAttachmentBusy = false;
        }
    }

    function caseCardHtml(c, idx, forModal) {
        const level = c.level || "P1";
        const levelClass = level === "P0" ? "mono-tag-active" : "";
        const editBtn = `<button class="chat-case-edit-btn" onclick="event.stopPropagation(); openGeneratedCaseEditor(${idx})" title="编辑此用例"><i class="bi bi-pencil"></i>编辑</button>`;
        if (forModal) {
            return `
                <div class="prompt-card" onclick="applyGeneratedCaseGoal(${idx})">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span class="small fw-semibold" style="font-size:12px;">${escapeHtml(c.module || "文档用例")}</span>
                        <span class="d-flex align-items-center gap-1">
                            <span class="mono-tag" style="font-size:9px;">${escapeHtml(level)}</span>
                            ${editBtn}
                        </span>
                    </div>
                    <div class="prompt-card-title">${escapeHtml(c.title || "")}</div>
                    <div class="prompt-card-desc">${escapeHtml(c.goal || "")}</div>
                    <div class="d-flex align-items-center gap-2 mt-1" style="font-size:10px;color:var(--text-muted);">
                        ${c.id ? `<span>${escapeHtml(c.id)}</span>` : ""}
                        ${c.precondition ? `<span class="text-truncate" title="${escapeHtml(c.precondition)}">前置：${escapeHtml(c.precondition)}</span>` : ""}
                    </div>
                </div>`;
        }
        return `
            <div class="suggest-template-card" onclick="applyGeneratedCaseGoal(${idx})" title="点击载入测试意图">
                <div class="suggest-icon-box"><i class="bi bi-file-earmark-text"></i></div>
                <div class="suggest-template-info">
                    <div class="suggest-template-title d-flex align-items-center gap-1">
                        <span class="text-truncate">${escapeHtml(c.title || "")}</span>
                        ${editBtn}
                    </div>
                    <div class="suggest-template-desc" title="${escapeHtml(c.goal || "")}">${escapeHtml(c.goal || "")}</div>
                </div>
                <div class="suggest-card-arrow"><i class="bi bi-arrow-up-right"></i></div>
            </div>`;
    }

    function renderGeneratedCases(cases, appLabel, showModal) {
        window._suggestedCasesCache = cases;
        const grid = document.getElementById("suggestCasesGrid");
        if (grid) {
            const hint = `<div class="chat-case-hint"><i class="bi bi-stars me-1"></i>以下用例由附件解析生成，点击卡片填入输入框，点击“编辑”可再次调整。</div>`;
            grid.innerHTML = hint + cases.map((c, idx) => caseCardHtml(c, idx, false)).join("");
        }

        const modalList = document.getElementById("modalSuggestedList");
        if (modalList) {
            modalList.innerHTML = cases.map((c, idx) => caseCardHtml(c, idx, true)).join("");
        }

        const labelEl = document.getElementById("suggestTargetAppLabel");
        if (labelEl) labelEl.innerText = `${appLabel || "待测应用"} · 附件生成`;

        if (showModal) {
            const modalEl = document.getElementById("suggestedCasesModal");
            if (modalEl && typeof bootstrap !== "undefined" && bootstrap.Modal) {
                bootstrap.Modal.getOrCreateInstance(modalEl).show();
            }
        }
    }

    function openGeneratedCaseEditor(idx) {
        const c = generatedCases[idx];
        if (!c) return;
        editingCaseIndex = idx;
        const badge = document.getElementById("genCaseEditBadge");
        if (badge) badge.innerText = c.id || `DOC-${String(idx + 1).padStart(2, "0")}`;
        document.getElementById("genCaseEditTitle").value = c.title || "";
        document.getElementById("genCaseEditLevel").value = (c.level || "P1").toUpperCase();
        document.getElementById("genCaseEditModule").value = c.module || "";
        document.getElementById("genCaseEditGoal").value = c.goal || "";
        document.getElementById("genCaseEditDesc").value = c.desc || "";
        document.getElementById("genCaseEditPrecondition").value = c.precondition || "";
        const modalEl = document.getElementById("generatedCaseEditModal");
        if (modalEl && typeof bootstrap !== "undefined" && bootstrap.Modal) {
            bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }
    }

    function saveGeneratedCaseEdit() {
        if (editingCaseIndex < 0 || !generatedCases[editingCaseIndex]) return;
        const title = (document.getElementById("genCaseEditTitle").value || "").trim();
        const goal = (document.getElementById("genCaseEditGoal").value || "").trim();
        if (!title || !goal) {
            alert("用例标题与测试目标不能为空。");
            return;
        }
        const c = generatedCases[editingCaseIndex];
        c.title = title;
        c.goal = goal;
        c.level = document.getElementById("genCaseEditLevel").value || "P1";
        c.module = (document.getElementById("genCaseEditModule").value || "").trim();
        c.desc = (document.getElementById("genCaseEditDesc").value || "").trim();
        c.precondition = (document.getElementById("genCaseEditPrecondition").value || "").trim();

        const modalEl = document.getElementById("generatedCaseEditModal");
        if (modalEl && typeof bootstrap !== "undefined" && bootstrap.Modal) {
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        }
        renderGeneratedCases(generatedCases, generatedCasesAppLabel, false);
        const status = document.getElementById("chatAttachmentStatus");
        if (status) {
            status.innerHTML = `<span class="text-success"><i class="bi bi-check-circle me-1"></i>用例已更新，可继续点击“编辑”再次修改或直接发起测试。</span>`;
        }
    }

    function applyGeneratedCaseGoal(idx) {
        const c = generatedCases[idx];
        if (!c) return;
        if (typeof fillPrompt === "function") {
            fillPrompt(c.goal || c.title || "");
        }
        const modalEl = document.getElementById("suggestedCasesModal");
        if (modalEl && typeof bootstrap !== "undefined" && bootstrap.Modal) {
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        }
    }

    function bindDropZone() {
        const box = document.getElementById("gptInputBox");
        if (!box || box._chatCaseDropBound) return;
        box._chatCaseDropBound = true;
        box.addEventListener("dragover", (e) => {
            e.preventDefault();
            box.classList.add("drag-over");
        });
        box.addEventListener("dragleave", (e) => {
            if (e.target === box || !box.contains(e.relatedTarget)) {
                box.classList.remove("drag-over");
            }
        });
        box.addEventListener("drop", (e) => {
            e.preventDefault();
            box.classList.remove("drag-over");
            const files = Array.from((e.dataTransfer && e.dataTransfer.files) || []);
            if (files.length) addChatAttachments(files);
        });
    }

    function bindUi() {
        const btn = document.getElementById("btnChatCaseGen");
        if (btn && !btn._bound) {
            btn._bound = true;
            btn.addEventListener("click", triggerChatAttachment);
        }
        const input = document.getElementById("chatAttachmentInput");
        if (input && !input._bound) {
            input._bound = true;
            input.addEventListener("change", handleChatAttachmentSelect);
        }
        bindDropZone();
    }

    // 挂载全局函数（供内联 onclick 调用）
    window.triggerChatAttachment = triggerChatAttachment;
    window.handleChatAttachmentSelect = handleChatAttachmentSelect;
    window.addChatAttachments = addChatAttachments;
    window.removeChatAttachment = removeChatAttachment;
    window.clearChatAttachments = clearChatAttachments;
    window.generateChatCasesFromAttachments = generateChatCasesFromAttachments;
    window.renderGeneratedCases = renderGeneratedCases;
    window.openGeneratedCaseEditor = openGeneratedCaseEditor;
    window.saveGeneratedCaseEdit = saveGeneratedCaseEdit;
    window.applyGeneratedCaseGoal = applyGeneratedCaseGoal;

    function init() {
        injectStyles();
        injectUi();
        bindUi();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
