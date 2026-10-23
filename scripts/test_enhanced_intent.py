import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.task_manager import TaskManager

tm = TaskManager()
sid = tm.create_session(
    goal="进入'委托服务'页面，点击'委托售房'，验证小区名称、期望售价与联系方式表单项正常渲染，并点击'免费发布'测试必填校验",
    device_ids=["2145189e"],
    test_mode="local",
    approval_mode="auto"
)

s = tm.get_session(sid)
th = next((b for b in s['timeline_blocks'] if b.get('type') == 'thought'), None)
print('--- 优化后意图推演 ---')
print('Duration:', th.get('duration'))
for b in th.get('bullets', []):
    print(f'[{b.get("tag")}]: {b.get("content")}')
    
todo = next((b for b in s['timeline_blocks'] if b.get('type') == 'todo_list'), None)
print('\n--- 优化后任务清单 ---')
print('Title:', todo.get('title'))
for it in todo.get('items', []):
    print(' +', it.get('title'), '->', it.get('desc'))
