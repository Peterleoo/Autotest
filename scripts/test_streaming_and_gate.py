import urllib.request
import urllib.parse
import json
import time

url = "http://127.0.0.1:8000/api/sessions/create"
payload = {
    "goal": "在首页点击'租房'进入租房主频道，点击'整租'标签进行切换，向下滑动加载两屏房源，断言月租金与户型信息展示完备",
    "devices": "mock_device_01",
    "test_mode": "local",
    "case_name": "auto_flow",
    "approval_mode": "auto"
}

data_encoded = urllib.parse.urlencode(payload).encode("utf-8")
req = urllib.request.Request(
    url,
    data=data_encoded,
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)

try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    sid = data.get("session_id")
    print(f"Created test session: {sid}")
    
    # 立即检查刚创建时的 session 结构
    res_s = urllib.request.urlopen(f"http://127.0.0.1:8000/api/sessions/{sid}")
    s_detail = json.loads(res_s.read())
    
    # 1. 检查 thinking 块
    th_blk = next((b for b in s_detail.get("timeline_blocks", []) if b.get("type") == "thought"), None)
    print("\n--- 1. Thinking Block ---")
    if th_blk:
        print(f"Duration: {th_blk.get('duration')}")
        for b in th_blk.get("bullets", []):
            print(f"[{b.get('tag')}]: {b.get('content')}")
            
    # 2. 检查 todo_list 块
    todo_blk = next((b for b in s_detail.get("timeline_blocks", []) if b.get("type") == "todo_list"), None)
    print("\n--- 2. TodoList Block ---")
    if todo_blk:
        print(f"Title: {todo_blk.get('title')}")
        print(f"Counts: {todo_blk.get('completed_count')}/{todo_blk.get('total_count')}")
        for it in todo_blk.get("items", []):
            print(f"  + {it.get('title')} [{it.get('status')}]: {it.get('desc')[:40]}")
            
    # 3. 轮询监控动态执行流 (每 0.8s 拉取一次，持续观察微观动作变化与门禁)
    print("\n--- 3. Real-time Action Streaming Observation ---")
    for loop in range(25):
        time.sleep(0.8)
        res_s = urllib.request.urlopen(f"http://127.0.0.1:8000/api/sessions/{sid}")
        s_detail = json.loads(res_s.read())
        tb = s_detail.get("timeline_blocks", [])
        
        step_execs = [b for b in tb if b.get("type") in ["step_execution", "step_result"]]
        summary_blk = next((b for b in tb if b.get("type") == "test_summary"), None)
        todo_cur = next((b for b in tb if b.get("type") == "todo_list"), None)
        
        comp_count = todo_cur.get('completed_count') if todo_cur else 0
        tot_count = todo_cur.get('total_count') if todo_cur else 0
        print(f"[Loop {loop+1:02d} - {time.strftime('%H:%M:%S')}] Status: {s_detail.get('status')} | Todo: {comp_count}/{tot_count} | ExecSteps: {len(step_execs)} | Summary Card Exists: {bool(summary_blk)}")
        
        if step_execs:
            latest_sc = step_execs[-1]
            acts = latest_sc.get("actions", [])
            print(f"   -> Latest: {latest_sc.get('title')} [{latest_sc.get('status')}] - {len(acts)} acts (act: {acts[-1].get('name') if acts else 'none'} [{acts[-1].get('status') if acts else ''}])")
            
        if summary_blk:
            print("\n>>> SUMMARY CARD APPEARED! Checking gate validity:")
            print(f"Is Todo 100% done? {comp_count == tot_count} ({comp_count}/{tot_count})")
            assert comp_count == tot_count, "Gate error: summary appeared before all steps done!"
            print("Gate check PASSED! Summary appeared ONLY after 100% completion.")
            break

except Exception as e:
    print(f"Error: {e}")
