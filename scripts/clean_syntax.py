from pathlib import Path

p = Path("core/task_manager.py")
text = p.read_text(encoding="utf-8")
text = text.replace('replace("\\", "/")', 'replace("\\\\", "/")')

lines = text.splitlines(keepends=True)
out = []
i = 0
while i < len(lines):
    line = lines[i]
    if 'raw_output="' in line and i + 1 < len(lines) and '".join' in lines[i+1]:
        out.append('            raw_output="\\n".join(dev_state["logs"]),\n')
        i += 2
        continue
    if '.replace("\\", "/")' in line:
        line = line.replace('.replace("\\", "/")', '.replace("\\\\", "/")')
    out.append(line)
    i += 1

p.write_text("".join(out), encoding="utf-8")
print("Cleaned up task_manager.py.")
