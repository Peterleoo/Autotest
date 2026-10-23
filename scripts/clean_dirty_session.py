import json
from pathlib import Path

p = Path("data/sessions/sess_1022_195524_2244.json")
if p.exists():
    data = json.loads(p.read_text(encoding="utf-8"))
    tb = data.get("timeline_blocks", [])
    
    # 清理重复的 step_execution
    seen_step_ids = set()
    cleaned_tb = []
    # 逆序保留最新的，再反转回来
    for b in reversed(tb):
        if b.get("type") == "step_execution":
            s_id = b.get("step_id")
            if s_id in seen_step_ids:
                continue
            seen_step_ids.add(s_id)
        cleaned_tb.append(b)
    cleaned_tb.reverse()
    
    # 同步 todo_list 中的 items 标题与 plan_steps 一致
    plan_steps = data.get("plan_steps", [])
    for b in cleaned_tb:
        if b.get("type") == "todo_list":
            b["items"] = [
                {
                    "title": s["title"],
                    "desc": s.get("desc", ""),
                    "status": s.get("status", "READY"),
                    "diff_type": "added"
                }
                for s in plan_steps
            ]
            b["total_count"] = len(plan_steps)
            b["completed_count"] = sum(1 for s in plan_steps if s.get("status") in ["COMPLETED", "PASS"])
            b["title"] = f"更新任务清单 · {b['completed_count']}/{b['total_count']} 已完成"
            
    data["timeline_blocks"] = cleaned_tb
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Fixed data/sessions/sess_1022_195524_2244.json.")
