import re
from pathlib import Path

BASE_DIR = Path("F:/Autotest")

# 1. 修改 core/task_manager.py
tm_p = BASE_DIR / "core/task_manager.py"
tm_code = tm_p.read_text(encoding="utf-8")

# 重构 _advance_session_step 中的步骤卡片处理逻辑，按 step_id 严格幂等寻址
old_advance_card_logic = '''                # 挂载/更新上一步微观动作链为 COMPLETED
                if step_index > 0:
                    prev_s = steps[step_index - 1]
                    prev_blk_id = f"blk_step_exec_0_{step_index}"
                    prev_card = next((b for b in session["timeline_blocks"] if b.get("block_id") == prev_blk_id), None)
                    p_title = prev_s.get("title", f"Step {step_index}")
                    p_desc = prev_s.get("desc", "")
                    actions = prev_s.get("actions") or [
                        {"type": "ocr", "name": "视觉感知", "desc": f"扫描定位【{p_title}】关联锚点", "observation": "文字置信度 98.5% · 成功定位组件中心坐标", "param": "OCR Match 0.985", "status": "COMPLETED"},
                        {"type": "tap", "name": "手势派发", "desc": f"注入原生触控手势：{p_desc[:24]}", "observation": "真机通道响应 18ms · 视图层级发生有效转场", "param": "tap(x, y)", "status": "COMPLETED"},
                        {"type": "assert", "name": "智能断言", "desc": "核验端侧业务状态与数据回包", "observation": "无 Crash · 无 ANR · 状态转移单调成立", "param": "PASS (Verified)", "status": "COMPLETED"}
                    ]
                    if not prev_card:
                        session["timeline_blocks"].append(TimelineManager.create_step_execution_block(
                            step_id=step_index,
                            title=f"Step {step_index}: {p_title} 验证通过 ✅",
                            actions=actions,
                            assertion_result=f"阶段断言达成：已成功完成并验证【{p_title}】",
                            status="COMPLETED",
                            duration="0.8s",
                            turn_id=0
                        ))
                    else:
                        prev_card["status"] = "COMPLETED"
                        prev_card["title"] = f"Step {step_index}: {p_title} 验证通过 ✅"
                        prev_card["assertion_result"] = f"阶段断言达成：已成功完成并验证【{p_title}】"
                        prev_card["actions"] = actions

                # 🚀 立即挂载当前步骤卡片 (RUNNING)，让用户实时看到正在执行该步骤！
                cur_step_num = step_index + 1
                cur_blk_id = f"blk_step_exec_0_{cur_step_num}"
                cur_card = next((b for b in session["timeline_blocks"] if b.get("block_id") == cur_blk_id), None)
                if not cur_card:
                    session["timeline_blocks"].append(TimelineManager.create_step_execution_block(
                        step_id=cur_step_num,
                        title=f"Step {cur_step_num}: {cur_step['title']}",
                        actions=[
                            {
                                "type": "ocr",
                                "name": "视觉感知",
                                "desc": f"扫描定位【{cur_step['title']}】目标交互热区",
                                "param": "OCR Scanning...",
                                "observation": "正在扫描屏幕组件与坐标...",
                                "status": "RUNNING"
                            }
                        ],
                        assertion_result="",
                        status="RUNNING",
                        duration="推进中",
                        turn_id=0
                    ))'''

new_advance_card_logic = '''                # 🚀 严格按 step_id 原地寻址与幂等去重，坚决杜绝同一步骤产生两个卡片！
                tb = session.setdefault("timeline_blocks", [])

                # 1. 推进上一步为 COMPLETED
                if step_index > 0:
                    prev_s = steps[step_index - 1]
                    p_title = prev_s.get("title", f"Step {step_index}")
                    p_desc = prev_s.get("desc", "")
                    actions = prev_s.get("actions") or [
                        {"type": "ocr", "name": "视觉感知", "desc": f"扫描定位【{p_title}】关联锚点", "observation": "文字置信度 98.5% · 成功定位组件中心坐标", "param": "OCR Match 0.985", "status": "COMPLETED"},
                        {"type": "tap", "name": "手势派发", "desc": f"注入原生触控手势：{p_desc[:24]}", "observation": "真机通道响应 18ms · 视图层级发生有效转场", "param": "tap(x, y)", "status": "COMPLETED"},
                        {"type": "assert", "name": "智能断言", "desc": "核验端侧业务状态与数据回包", "observation": "无 Crash · 无 ANR · 状态转移单调成立", "param": "PASS (Verified)", "status": "COMPLETED"}
                    ]
                    
                    # 查找该 step_id 的所有历史卡片，清理多余重复项，只保留一个
                    matching_prev = [b for b in tb if b.get("type") in ["step_execution", "step_result"] and b.get("step_id") == step_index]
                    if matching_prev:
                        # 原地更新第一个
                        prev_card = matching_prev[0]
                        prev_card["block_id"] = f"blk_step_exec_0_{step_index}"
                        prev_card["status"] = "COMPLETED"
                        prev_card["title"] = f"Step {step_index}: {p_title} 验证通过 ✅"
                        prev_card["assertion_result"] = f"阶段断言达成：已成功完成并验证【{p_title}】"
                        prev_card["actions"] = actions
                        prev_card["duration"] = "0.8s"
                        # 移除多余的重复卡片
                        for extra in matching_prev[1:]:
                            if extra in tb:
                                tb.remove(extra)
                    else:
                        tb.append(TimelineManager.create_step_execution_block(
                            step_id=step_index,
                            title=f"Step {step_index}: {p_title} 验证通过 ✅",
                            actions=actions,
                            assertion_result=f"阶段断言达成：已成功完成并验证【{p_title}】",
                            status="COMPLETED",
                            duration="0.8s",
                            turn_id=0
                        ))

                # 2. 激活当前步骤卡片为 RUNNING
                cur_step_num = step_index + 1
                matching_cur = [b for b in tb if b.get("type") in ["step_execution", "step_result"] and b.get("step_id") == cur_step_num]
                if matching_cur:
                    cur_card = matching_cur[0]
                    cur_card["block_id"] = f"blk_step_exec_0_{cur_step_num}"
                    cur_card["status"] = "RUNNING"
                    cur_card["title"] = f"Step {cur_step_num}: {cur_step['title']}"
                    for extra in matching_cur[1:]:
                        if extra in tb:
                            tb.remove(extra)
                else:
                    tb.append(TimelineManager.create_step_execution_block(
                        step_id=cur_step_num,
                        title=f"Step {cur_step_num}: {cur_step['title']}",
                        actions=[
                            {
                                "type": "ocr",
                                "name": "视觉感知",
                                "desc": f"扫描定位【{cur_step['title']}】目标交互热区",
                                "param": "OCR Scanning...",
                                "observation": "正在扫描屏幕组件与坐标...",
                                "status": "RUNNING"
                            }
                        ],
                        assertion_result="",
                        status="RUNNING",
                        duration="推进中",
                        turn_id=0
                    ))'''

if old_advance_card_logic in tm_code:
    tm_code = tm_code.replace(old_advance_card_logic, new_advance_card_logic)
    print("Updated _advance_session_step idempotent card logic.")
else:
    print("WARNING: Could not find old_advance_card_logic")

tm_p.write_text(tm_code, encoding="utf-8")


# ================= 2. 修改 web/templates/index.html =================
idx_p = BASE_DIR / "web/templates/index.html"
idx_code = idx_p.read_text(encoding="utf-8")

old_render_loop = '''            const blocks = sessionData.timeline_blocks || [];
            blocks.forEach(blk => {
                const blkId = blk.block_id;
                let existingEl = document.getElementById(blkId);
                if (!existingEl) {
                    const html = buildBlockHtml(blk, sessionData);
                    if (html) {
                        flow.insertAdjacentHTML("beforeend", html);
                        window._renderedBlockIds.add(blkId);
                    }
                } else {'''

new_render_loop = '''            // 🛡️ 步骤卡片防重免疫：同一 step_id 无论 block_id 为何，界面上只保留一个最新容器！
            const rawBlocks = sessionData.timeline_blocks || [];
            const seenSteps = new Set();
            const blocks = [];
            
            // 逆序筛选出最新的 step 卡片，再顺序排布
            for (let i = rawBlocks.length - 1; i >= 0; i--) {
                const b = rawBlocks[i];
                if (b.type === "step_execution" || b.type === "step_result") {
                    const sId = b.step_id || 1;
                    if (seenSteps.has(sId)) continue;
                    seenSteps.add(sId);
                }
                blocks.unshift(b);
            }

            blocks.forEach(blk => {
                const blkId = blk.block_id;
                let existingEl = document.getElementById(blkId);
                
                // 兼容根据 step_id 定位已渲染节点
                if (!existingEl && (blk.type === "step_execution" || blk.type === "step_result")) {
                    existingEl = flow.querySelector(`.stream-step-card[data-step-id="${blk.step_id}"]`);
                }

                if (!existingEl) {
                    const html = buildBlockHtml(blk, sessionData);
                    if (html) {
                        flow.insertAdjacentHTML("beforeend", html);
                        window._renderedBlockIds.add(blkId);
                    }
                } else {'''

if old_render_loop in idx_code:
    idx_code = idx_code.replace(old_render_loop, new_render_loop)
    print("Updated render loop with step de-duplication.")
else:
    print("WARNING: Could not find old_render_loop in index.html")

# 为 stream-step-card 加上 data-step-id 属性
old_step_card_tag = '<div class="stream-step-card ${statusClass}" id="${blk.block_id}">'
new_step_card_tag = '<div class="stream-step-card ${statusClass}" id="${blk.block_id}" data-step-id="${blk.step_id || 1}">'
if old_step_card_tag in idx_code:
    idx_code = idx_code.replace(old_step_card_tag, new_step_card_tag)
    print("Added data-step-id attribute to step cards.")

idx_p.write_text(idx_code, encoding="utf-8")
print("Finished updating task_manager.py and index.html.")
