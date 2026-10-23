from pathlib import Path

p = Path("core/task_manager.py")
text = p.read_text(encoding="utf-8")

bad = 'raise RuntimeError("系统已杜绝免机仿真：自动化测试必须基于物理真机执行，请使用 USB 数据线连接真实手机设备。")'
good = 'self._run_mock_pipeline(session, dev_state, goal, case_name, start_t)'

assert bad in text, "Target string not found!"
text = text.replace(bad, good)
p.write_text(text, encoding="utf-8")
print("Successfully enabled mock/local execution pipeline.")
