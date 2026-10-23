from pathlib import Path

p = Path("web/templates/index.html")
code = p.read_text(encoding="utf-8")

old_gate = '''                const steps = sessionData.plan_steps || [];
                const total = steps.length;
                const completed = steps.filter(s => s.status === "COMPLETED" || s.status === "PASS").length;
                const isAllStepsDone = (total > 0 && completed === total);
                
                if (!isFinished || sessionData.status === "RUNNING" || !isAllStepsDone) {
                    return "";
                }'''

new_gate = '''                const steps = sessionData.plan_steps || [];
                const total = steps.length;
                const completed = steps.filter(s => s.status === "COMPLETED" || s.status === "PASS").length;
                const isAllStepsDone = (total > 0 && completed === total);
                
                // 🛡️ 绝对防线：强行校验用户界面上看到的任务清单 (TodoList) 是否 100% 达成！
                const todoBlk = (sessionData.timeline_blocks || []).find(b => b.type === "todo_list");
                let isTodoAllDone = true;
                if (todoBlk && Array.isArray(todoBlk.items) && todoBlk.items.length > 0) {
                    const uncompletedItems = todoBlk.items.filter(it => it.status !== "COMPLETED" && it.status !== "PASS");
                    if (uncompletedItems.length > 0) {
                        isTodoAllDone = false;
                    }
                }

                if (!isFinished || sessionData.status === "RUNNING" || !isAllStepsDone || !isTodoAllDone) {
                    return "";
                }'''

if old_gate in code:
    code = code.replace(old_gate, new_gate)
    p.write_text(code, encoding="utf-8")
    print("Enhanced index.html summary gate with isTodoAllDone successfully.")
else:
    print("WARNING: Could not find old_gate in index.html")
