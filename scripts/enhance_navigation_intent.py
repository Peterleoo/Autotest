from pathlib import Path
import re

p = Path("core/task_manager.py")
code = p.read_text(encoding="utf-8")

# 1. 修复断言标题截断
code = code.replace('f"核心断言: {m_target[:18]}"', 'f"核心断言: {m_target[:28]}"')

# 2. 增强意图推演中的业务寻路策略解析
old_intent_bullet = '''        step_titles = [s["title"] for s in plan_steps]
        key_steps_str = " ➔ ".join(step_titles[1:-1][:3]) if len(step_titles) > 2 else "业务流程推进"
        assert_step = next((s["title"] for s in plan_steps if "断言" in s["title"]), "核心业务指标")
        thinking_data = {
            "duration": duration_str,
            "bullets": [
                {"tag": "业务意图推演", "content": f"深度解析测试目标【{goal}】，智能拆解为 {len(plan_steps)} 个端侧业务阶段：{key_steps_str}。"},
                {"tag": "跨端定位策略", "content": f"分配物理真机 [{', '.join(device_ids)}]，锁定动态视觉 OCR 感知与原生手势双通道复合定位。"},
                {"tag": "断言与防抖策略", "content": f"针对【{assert_step}】启用界面渲染防抖等待与列表幂等校验，确保验证结果确定性。"}
            ]
        }'''

new_intent_bullet = '''        step_titles = [s["title"] for s in plan_steps]
        key_steps_str = " ➔ ".join(step_titles[1:-1][:3]) if len(step_titles) > 2 else "业务流程推进"
        assert_step = next((s["title"] for s in plan_steps if "断言" in s["title"]), "核心业务指标")
        
        # 智能寻路推演：分析目标属于哪类业务场景（找房/业主委托/交易表单/个人中心）
        g_low = goal.lower()
        if any(k in g_low for k in ["委托", "卖房", "出租", "放盘"]):
            nav_strategy = "【业主委托链路】入口寻路推演：1. 优先扫描首页金刚区核心功能位（识别'委托服务/我要卖房'图文控件）；2. 若首屏未检出，降级至底栏【我的】个人中心定位'业主服务/房屋委托'。"
        elif any(k in g_low for k in ["搜索", "二手房", "租房", "新房", "商圈"]):
            nav_strategy = "【买房/租房检索链路】入口寻路推演：首选首页金刚区核心频道入口，进入列表后通过顶栏搜索框或多维筛选器流转。"
        else:
            nav_strategy = f"【业务闭环链路】针对【{key_steps_str}】采用页面组件树感知与 OCR 双通道动态寻路。"

        thinking_data = {
            "duration": duration_str,
            "bullets": [
                {"tag": "业务意图推演", "content": f"深度解析测试目标【{goal}】，拆解为 {len(plan_steps)} 个业务阶段：{key_steps_str}。"},
                {"tag": "入口寻路策略", "content": nav_strategy},
                {"tag": "断言与防抖策略", "content": f"针对【{assert_step}】启用视图状态核验与表单响应防抖，确保字段与校验结果确定性。"}
            ]
        }'''

if old_intent_bullet in code:
    code = code.replace(old_intent_bullet, new_intent_bullet)
    print("Replaced thinking_data navigation strategy successfully.")
else:
    print("WARNING: Could not find old_intent_bullet")

p.write_text(code, encoding="utf-8")
print("task_manager.py saved navigation update.")
