// 🌟 PM-product 风格安全决策门弹窗调度
function showPmDecisionModal(title, desc, context) {
    if (title) document.getElementById('pmDecisionTitle').innerText = title;
    if (desc) document.getElementById('pmDecisionDesc').innerText = desc;
    if (context) document.getElementById('pmDecisionContext').innerText = context;
    const modalEl = document.getElementById('pmDecisionModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }
}

function resolvePmDecision(decisionType) {
    const modalEl = document.getElementById('pmDecisionModal');
    if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
    }
    console.log('✔ 已执行安全决策决断:', decisionType);
    if (typeof showToast === 'function') {
        showToast('已下达安全决断: ' + decisionType, 'success');
    }
}

// 🌟 0 Token 毫秒级原生用例回放 (直接调起 Pytest 执行固化脚本)
async function replaySolidifiedCase(safeRef, btnEl) {
    if (!safeRef) {
        alert('缺少测试脚本路径');
        return;
    }
    const origHtml = btnEl ? btnEl.innerHTML : '';
    if (btnEl) {
        btnEl.disabled = true;
        btnEl.innerHTML = '<span class="spinner-border spinner-border-sm me-1" style="width:11px;height:11px;"></span> 0-Token 回放中...';
    }

    try {
        const res = await fetch('/api/deliverables/replay', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ safeRef: safeRef, device_id: (typeof getPipTargetDeviceId === 'function' ? getPipTargetDeviceId() : null) || 'auto' })
        });
        const data = await res.json();
        if (btnEl) {
            btnEl.disabled = false;
            btnEl.innerHTML = origHtml;
        }

        const durText = (data.duration !== undefined && data.duration !== null) ? `${data.duration}s` : '0s';
        if (data.success && data.passed) {
            alert(`🎉 [0 Token 秒级回测成功！]\n耗时: ${durText}\n状态: PASS\n全链路断言 100% 达标通过！`);
        } else {
            const failReason = data.error || data.summary || (data.output ? data.output.slice(0, 300) : "用例执行受阻或断言未达成");
            alert(`⚠️ [回测未通过 / 异常诊断]\n耗时: ${durText}\n状态: FAIL\n诊断原因: ${failReason}`);
        }
    } catch (e) {
        if (btnEl) {
            btnEl.disabled = false;
            btnEl.innerHTML = origHtml;
        }
        alert('回放触发异常: ' + e);
    }
}
