import re
from pathlib import Path

BASE_DIR = Path("F:/Autotest")

# ================= 修复 1: timeline_manager.py 固定 block_id =================
tlm_p = BASE_DIR / "core/timeline_manager.py"
tlm_code = tlm_p.read_text(encoding="utf-8")

old_id_gen = '"block_id": f"blk_step_exec_{turn_id}_{step_id}_{uuid.uuid4().hex[:6]}",'
new_id_gen = '"block_id": f"blk_step_exec_{turn_id}_{step_id}",'

if old_id_gen in tlm_code:
    tlm_code = tlm_code.replace(old_id_gen, new_id_gen)
    tlm_p.write_text(tlm_code, encoding="utf-8")
    print("Fixed 1: Removed random UUID from create_step_execution_block.")
else:
    print("WARNING: Could not find old_id_gen in timeline_manager.py")


# ================= 修复 2 & 3: task_manager.py =================
tm_p = BASE_DIR / "core/task_manager.py"
tm_code = tm_p.read_text(encoding="utf-8")

# 修复 2: _async_enrich_thinking 同步更新 todo_list 和 thought 块
old_enrich = '''                    if not has_progressed and ai_steps:
                        cur_sess["plan_steps"] = ai_steps
                    self._save_session(session_id)'''

new_enrich = '''                    if not has_progressed and ai_steps:
                        cur_sess["plan_steps"] = ai_steps
                        # 🚀 原子同步更新 timeline_blocks 中的 todo_list 与 thought 块，杜绝双轨制脱节！
                        tb = cur_sess.setdefault("timeline_blocks", [])
                        for b in tb:
                            if b.get("type") == "todo_list":
                                b["total_count"] = len(ai_steps)
                                b["title"] = f"更新任务清单 · 0/{len(ai_steps)} 已完成"
                                b["items"] = [
                                    {
                                        "title": s["title"],
                                        "desc": s.get("desc", ""),
                                        "status": s.get("status", "READY"),
                                        "diff_type": "added"
                                    }
                                    for s in ai_steps
                                ]
                            elif b.get("type") == "thought" and ai_thinking:
                                b["bullets"] = ai_thinking.get("bullets", b.get("bullets", []))
                                if ai_thinking.get("duration"):
                                    b["duration"] = ai_thinking["duration"]
                    self._save_session(session_id)'''

if old_enrich in tm_code:
    tm_code = tm_code.replace(old_enrich, new_enrich)
    print("Fixed 2: Synchronized todo_list block in _async_enrich_thinking.")
else:
    print("WARNING: Could not find old_enrich in task_manager.py")

# 修复 3: 删除 1405 行的暴力拉满步数，按实际真实执行步数收敛
old_force_complete = '''        if is_success:
            session["is_success"] = True
            session["error_message"] = ""
            cur_idx = max(cur_idx, len(session.get("plan_steps", [])) - 1)'''

new_force_complete = '''        # 🛡️ 事实核验：只有真正跑完全部步骤或明确目标达成，才算全链路完成；严禁中途退出暴力拉满步数！
        all_steps = session.get("plan_steps", [])
        is_all_steps_reached = (cur_idx >= len(all_steps) - 1) and (len(all_steps) > 0)
        truly_success = has_goal_achieved or (proc.returncode == 0 and is_all_steps_reached)
        
        is_success = truly_success
        dev_state["success"] = is_success
        dev_state["status"] = "PASS" if is_success else "FAIL"

        if is_success:
            session["is_success"] = True
            session["error_message"] = ""
            cur_idx = len(all_steps) - 1
        else:
            session["is_success"] = False'''

if old_force_complete in tm_code:
    tm_code = tm_code.replace(old_force_complete, new_force_complete)
    print("Fixed 3: Removed false max(cur_idx, len - 1) step falsification.")
else:
    print("WARNING: Could not find old_force_complete in task_manager.py")

# 修复 4: _advance_session_step 里的卡片寻址，统一步骤卡片 block_id = f"blk_step_exec_0_{step_no}"
old_step_find = 'cur_blk_id = f"blk_stepres_0_{cur_step_num}"'
new_step_find = 'cur_blk_id = f"blk_step_exec_0_{cur_step_num}"'
if old_step_find in tm_code:
    tm_code = tm_code.replace(old_step_find, new_step_find)
    print("Fixed 4: Aligned cur_blk_id to blk_step_exec_0_{cur_step_num}.")

old_prev_find = 'prev_blk_id = f"blk_stepres_0_{step_index}"'
new_prev_find = 'prev_blk_id = f"blk_step_exec_0_{step_index}"'
if old_prev_find in tm_code:
    tm_code = tm_code.replace(old_prev_find, new_prev_find)
    print("Fixed 5: Aligned prev_blk_id to blk_step_exec_0_{step_index}.")

tm_p.write_text(tm_code, encoding="utf-8")
print("task_manager.py and timeline_manager.py saved successfully.")
