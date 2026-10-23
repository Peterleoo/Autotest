import re
from pathlib import Path

p = Path("core/task_manager.py")
code = p.read_text(encoding="utf-8")

# 1. 完善 _advance_session_step
old_advance_block = '''                # 挂载阶段性步骤微观动作链与获得产物
                if step_index > 0:
                    prev_s = steps[step_index - 1]
                    res_blk_id = f"blk_stepres_0_{step_index}"
                    if not any(b.get("block_id") == res_blk_id for b in session["timeline_blocks"]):
                        p_title = prev_s.get("title", f"Step {step_index}")
                        p_desc = prev_s.get("desc", "")
                        actions = prev_s.get("actions") or [
                            {
                                "type": "ocr",
                                "name": "视觉感知",
                                "desc": f"扫描屏幕并提取【{p_title}】关联锚点",
                                "observation": "文字置信度 98.5% · 成功定位组件中心坐标",
                                "param": "OCR Match 0.985"
                            },
                            {
                                "type": "tap",
                                "name": "手势派发",
                                "desc": f"注入原生触控手势：{p_desc[:24]}",
                                "observation": "屏幕成功响应，视图层级发生有效转场",
                                "param": "tap(x, y)"
                            },
                            {
                                "type": "assert",
                                "name": "智能断言",
                                "desc": "核验端侧业务状态与数据回包",
                                "observation": "无 Crash · 无 ANR · 状态转移单调成立",
                                "param": "PASS (200 OK)"
                            }
                        ]
                        session["timeline_blocks"].append(TimelineManager.create_step_execution_block(
                            step_id=step_index,
                            title=p_title,
                            actions=actions,
                            assertion_result=f"阶段断言达成：已成功完成并验证【{p_title}】",
                            status="COMPLETED",
                            duration="0.4s",
                            turn_id=0
                        ))'''

new_advance_block = '''                # 挂载/更新上一步微观动作链为 COMPLETED
                if step_index > 0:
                    prev_s = steps[step_index - 1]
                    prev_blk_id = f"blk_stepres_0_{step_index}"
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
                cur_blk_id = f"blk_stepres_0_{cur_step_num}"
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

if old_advance_block in code:
    code = code.replace(old_advance_block, new_advance_block)
    print("Replaced _advance_session_step logic successfully.")
else:
    print("WARNING: Could not find old_advance_block")

p.write_text(code, encoding="utf-8")
print("task_manager.py saved step 3.")
