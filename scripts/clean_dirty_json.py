import json
from pathlib import Path

p = Path("data/sessions/sess_1022_195524_2244.json")
if p.exists():
    data = json.loads(p.read_text(encoding="utf-8"))
    tb = data.get("timeline_blocks", [])
    
    # 彻底清理多余的步骤块，同一步骤只保留最新的
    cleaned_tb = []
    seen_steps = set()
    for b in reversed(tb):
        if b.get("type") in ["step_execution", "step_result"]:
            s_id = b.get("step_id")
            if s_id in seen_steps:
                continue
            seen_steps.add(s_id)
        cleaned_tb.append(b)
    cleaned_tb.reverse()
    
    data["timeline_blocks"] = cleaned_tb
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Cleaned sess_1022_195524_2244 blocks successfully.")
