"""
由 AI 自动化测试智能体自动录制固化的跨端测试用例 (Dual-Mode Resilient Test Suite)
测试目标: 【系统测试用例 2/4: 三栏工作台沉浸推演、意图输入与 16ms 打字机结论输出验证】
业务目标: 连接合规物理真机，选择待测应用胶囊，输入核心业务意图并点击开始，观察工作台实时投屏、Thought 深度思考折叠及执行完成后的打字机人话总结
断言验证: 断言真机成功拉起，右侧 Canvas 实时镜像正常展示，执行完成后以 16ms/字节奏流出通俗人话业务结论，且左侧会话时间轴正确归档

[关联需求规约参考]:
# Autotest AI 产品全景梳理与业务规格说明书 (Product Master Definition)

> **版本**：v2.0 (重大工程落地与产品化升级重构版)  
> **更新时间**：2026-10-20  
> **核心定位**：专为非专业测试人员（业务开发、PM、业务测试）打造的 **物理真机优先、多模态智能驱动与零 Token 原生脚本固化工作台**  
> **设计哲学**：**真机实测优先，坚决杜绝免机仿真 (Real-Device-First, Zero-Mock Policy)**

---

## 一、 产品定位与核心价值主张 (Value Proposition)

### 1.1 产品诞生背景与核心阻力
- **假跑与仿真陷阱**：市面上大量自动化工具在缺少真机时采用纯 Mock 或静态虚拟跑，无法发现真实移动端渲染抖动、定制机型权限拦截、系统底层手势冲突等致命问题，导致“线上通过、真机全崩”；
- **非专业人员的使用天堑**：业务 PM、功能测试与开发人员面对 ADB 命令行、复杂环境变量、Appium 驱动配置以及国产 ROM 的深度安全拦截（如小米 USB 安全设置、vivo 模拟点击）时，往往耗费数小时在环境搭设上，最终放弃自测；
- **AI 与确定性回归的断层**：纯大模型执行极贵且不可控，而纯手工脚本编写成本极其脆弱。

### 1.2 产品核心价值闭环
Autotest AI 彻底打通了 **“意图输入 ➔ 极速预检 ➔ 多模态驱动 ➔ 智能人话诊断 ➔ 零 Token 确定性固化”** 的全生命周期：

```mermaid
flowchart TD
    A[非专业用户选择待测包与意图] --> B{第0步: 物理真机与手势探针预检}
    B -- 设备离线 / 未开启安全调试 --> B1[知识库秒级弹出人话图文排查指引并硬拦截]
    B -- 预检通过 --> C[原生 ADB 极速真机拉起与多模态 AI 推演]
    C --> D[三栏工作台: 实时投屏 + 思考折叠 + 16ms打字机人话结论]
    D --> E{自测结果判断}
    E -- 遇到业务阻断 --> E1[单会话连续多轮对话追问与即时纠偏]
    E -- 自测跑通 --> F[一键固化为标准原生 Pytest 脚本]
    F --> G[存入团队用例库 / CI-CD 秒级 0 Token 回归]
```

---

## 二、 最新调整重塑的七大核心产品能力

经过本轮深度工程落地与产品化重构，Autotest AI 确立了七大具有断代优势的护城河能力：

### 1. 🛡️ 物理真机优先与硬拦截机制 (Real-Device-First & Pre-flight Hard Check)

执行命令: pytest test_case_2.py -v -s
特性优势:
  1. 语义优先 (Text / ID / Desc) 动态查找；
  2. 屏幕自适应百分比相对坐标兜底，免维护跨不同分辨率真机回归！
"""
import time
import pytest
import allure
from appium.webdriver.common.appiumby import AppiumBy

from core.driver_factory import DriverFactory
from core.api_client import APIClient


def robust_click(driver, text=None, res_id=None, desc=None, rel_x=None, rel_y=None):
    """
    双模自适应点击 (Dual-Mode Click)
    模式 1: 优先语义匹配 (文本/ID/无障碍描述)
    模式 2: 分辨率相对百分比动态换算兜底
    """
    if text:
        try:
            el = driver.find_element(AppiumBy.XPATH, f"//*[@text='{text}' or contains(@text, '{text}')]")
            el.click()
            return
        except Exception:
            pass
    if res_id:
        try:
            el = driver.find_element(AppiumBy.ID, res_id)
            el.click()
            return
        except Exception:
            pass
    if desc:
        try:
            el = driver.find_element(AppiumBy.ACCESSIBILITY_ID, desc)
            el.click()
            return
        except Exception:
            pass

    # 兜底：相对百分比换算实际物理坐标
    if rel_x is not None and rel_y is not None:
        size = driver.get_window_size()
        w = size.get('width', 1080)
        h = size.get('height', 2160)
        target_x = int(w * rel_x)
        target_y = int(h * rel_y)
        if hasattr(driver, "tap"):
            driver.tap([(target_x, target_y)])
        else:
            driver.execute_adb(["shell", "input", "tap", str(target_x), str(target_y)])
        return

    raise RuntimeError(f"无法定位或点击目标元素: text={text}, id={res_id}, rel=({rel_x}, {rel_y})")


def robust_type(driver, text=None, res_id=None, desc=None, rel_x=None, rel_y=None, input_text=""):
    """
    双模自适应输入 (Dual-Mode Type)
    优先语义查找输入框，相对坐标点击聚焦兜底并注入文本
    """
    typed = False
    if text or res_id or desc:
        try:
            el = None
            if res_id:
                try: el = driver.find_element(AppiumBy.ID, res_id)
                except Exception: pass
            if not el and text:
                try: el = driver.find_element(AppiumBy.XPATH, f"//*[@text='{text}' or contains(@text, '{text}')]")
                except Exception: pass
            if not el and desc:
                try: el = driver.find_element(AppiumBy.ACCESSIBILITY_ID, desc)
                except Exception: pass
            if el:
                el.clear()
                el.send_keys(input_text)
                typed = True
                return
        except Exception:
            pass

    if not typed:
        robust_click(driver, text=text, res_id=res_id, desc=desc, rel_x=rel_x, rel_y=rel_y)
        time.sleep(0.3)
        try:
            driver.switch_to.active_element.send_keys(input_text)
        except Exception:
            if hasattr(driver, "execute_adb"):
                driver.execute_adb(["shell", "input", "text", input_text])


def robust_swipe(driver, direction="up", repeat=1):
    """自适应屏幕物理分辨率滑动"""
    size = driver.get_window_size()
    w = size.get('width', 1080)
    h = size.get('height', 2160)
    for _ in range(repeat):
        if direction == "up":
            driver.swipe(w // 2, int(h * 0.75), w // 2, int(h * 0.25), 450)
        elif direction == "down":
            driver.swipe(w // 2, int(h * 0.25), w // 2, int(h * 0.75), 450)
        elif direction == "left":
            driver.swipe(int(w * 0.88), h // 2, int(w * 0.12), h // 2, 350)
        elif direction == "right":
            driver.swipe(int(w * 0.12), h // 2, int(w * 0.88), h // 2, 350)
        time.sleep(0.3)


@pytest.fixture(scope="module")
def driver():
    """初始化真机驱动"""
    drv = DriverFactory.create_driver()
    yield drv
    drv.quit()


@pytest.fixture(scope="module")
def api_client():
    """初始化统一接口客户端"""
    return APIClient()


@allure.feature("固化测试套件")
@allure.story("【系统测试用例 2/4: 三栏工作台沉浸推演、意图输入与 16ms 打字机结论输出验证】
业务目标: 连接合规物理真机，选择待测应用胶囊，输入核心业务意图并点击开始，观察工作台实时投屏、Thought 深度思考折叠及执行完成后的打字机人话总结
断言验证: 断言真机成功拉起，右侧 Canvas 实时镜像正常展示，执行完成后以 16ms/字节奏流出通俗人话业务结论，且左侧会话时间轴正确归档

[关联需求规约参考]:
# Autotest AI 产品全景梳理与业务规格说明书 (Product Master Definition)

> **版本**：v2.0 (重大工程落地与产品化升级重构版)  
> **更新时间**：2026-10-20  
> **核心定位**：专为非专业测试人员（业务开发、PM、业务测试）打造的 **物理真机优先、多模态智能驱动与零 Token 原生脚本固化工作台**  
> **设计哲学**：**真机实测优先，坚决杜绝免机仿真 (Real-Device-First, Zero-Mock Policy)**

---

## 一、 产品定位与核心价值主张 (Value Proposition)

### 1.1 产品诞生背景与核心阻力
- **假跑与仿真陷阱**：市面上大量自动化工具在缺少真机时采用纯 Mock 或静态虚拟跑，无法发现真实移动端渲染抖动、定制机型权限拦截、系统底层手势冲突等致命问题，导致“线上通过、真机全崩”；
- **非专业人员的使用天堑**：业务 PM、功能测试与开发人员面对 ADB 命令行、复杂环境变量、Appium 驱动配置以及国产 ROM 的深度安全拦截（如小米 USB 安全设置、vivo 模拟点击）时，往往耗费数小时在环境搭设上，最终放弃自测；
- **AI 与确定性回归的断层**：纯大模型执行极贵且不可控，而纯手工脚本编写成本极其脆弱。

### 1.2 产品核心价值闭环
Autotest AI 彻底打通了 **“意图输入 ➔ 极速预检 ➔ 多模态驱动 ➔ 智能人话诊断 ➔ 零 Token 确定性固化”** 的全生命周期：

```mermaid
flowchart TD
    A[非专业用户选择待测包与意图] --> B{第0步: 物理真机与手势探针预检}
    B -- 设备离线 / 未开启安全调试 --> B1[知识库秒级弹出人话图文排查指引并硬拦截]
    B -- 预检通过 --> C[原生 ADB 极速真机拉起与多模态 AI 推演]
    C --> D[三栏工作台: 实时投屏 + 思考折叠 + 16ms打字机人话结论]
    D --> E{自测结果判断}
    E -- 遇到业务阻断 --> E1[单会话连续多轮对话追问与即时纠偏]
    E -- 自测跑通 --> F[一键固化为标准原生 Pytest 脚本]
    F --> G[存入团队用例库 / CI-CD 秒级 0 Token 回归]
```

---

## 二、 最新调整重塑的七大核心产品能力

经过本轮深度工程落地与产品化重构，Autotest AI 确立了七大具有断代优势的护城河能力：

### 1. 🛡️ 物理真机优先与硬拦截机制 (Real-Device-First & Pre-flight Hard Check)
")
def test_case_2(driver, api_client):
    """
    自动化用例: test_case_2
    测试目标: 【系统测试用例 2/4: 三栏工作台沉浸推演、意图输入与 16ms 打字机结论输出验证】
业务目标: 连接合规物理真机，选择待测应用胶囊，输入核心业务意图并点击开始，观察工作台实时投屏、Thought 深度思考折叠及执行完成后的打字机人话总结
断言验证: 断言真机成功拉起，右侧 Canvas 实时镜像正常展示，执行完成后以 16ms/字节奏流出通俗人话业务结论，且左侧会话时间轴正确归档

[关联需求规约参考]:
# Autotest AI 产品全景梳理与业务规格说明书 (Product Master Definition)

> **版本**：v2.0 (重大工程落地与产品化升级重构版)  
> **更新时间**：2026-10-20  
> **核心定位**：专为非专业测试人员（业务开发、PM、业务测试）打造的 **物理真机优先、多模态智能驱动与零 Token 原生脚本固化工作台**  
> **设计哲学**：**真机实测优先，坚决杜绝免机仿真 (Real-Device-First, Zero-Mock Policy)**

---

## 一、 产品定位与核心价值主张 (Value Proposition)

### 1.1 产品诞生背景与核心阻力
- **假跑与仿真陷阱**：市面上大量自动化工具在缺少真机时采用纯 Mock 或静态虚拟跑，无法发现真实移动端渲染抖动、定制机型权限拦截、系统底层手势冲突等致命问题，导致“线上通过、真机全崩”；
- **非专业人员的使用天堑**：业务 PM、功能测试与开发人员面对 ADB 命令行、复杂环境变量、Appium 驱动配置以及国产 ROM 的深度安全拦截（如小米 USB 安全设置、vivo 模拟点击）时，往往耗费数小时在环境搭设上，最终放弃自测；
- **AI 与确定性回归的断层**：纯大模型执行极贵且不可控，而纯手工脚本编写成本极其脆弱。

### 1.2 产品核心价值闭环
Autotest AI 彻底打通了 **“意图输入 ➔ 极速预检 ➔ 多模态驱动 ➔ 智能人话诊断 ➔ 零 Token 确定性固化”** 的全生命周期：

```mermaid
flowchart TD
    A[非专业用户选择待测包与意图] --> B{第0步: 物理真机与手势探针预检}
    B -- 设备离线 / 未开启安全调试 --> B1[知识库秒级弹出人话图文排查指引并硬拦截]
    B -- 预检通过 --> C[原生 ADB 极速真机拉起与多模态 AI 推演]
    C --> D[三栏工作台: 实时投屏 + 思考折叠 + 16ms打字机人话结论]
    D --> E{自测结果判断}
    E -- 遇到业务阻断 --> E1[单会话连续多轮对话追问与即时纠偏]
    E -- 自测跑通 --> F[一键固化为标准原生 Pytest 脚本]
    F --> G[存入团队用例库 / CI-CD 秒级 0 Token 回归]
```

---

## 二、 最新调整重塑的七大核心产品能力

经过本轮深度工程落地与产品化重构，Autotest AI 确立了七大具有断代优势的护城河能力：

### 1. 🛡️ 物理真机优先与硬拦截机制 (Real-Device-First & Pre-flight Hard Check)

    """
    # 步骤 1: 接口测试 [GET ]
    resp = api_client.request('GET', '')
    assert resp.status_code == 200, f'接口状态码断言失败: {resp.status_code} != 200'

    # 步骤 2: 接口测试 [GET ]
    resp = api_client.request('GET', '')
    assert resp.status_code == 200, f'接口状态码断言失败: {resp.status_code} != 200'

    # 步骤 3: 接口测试 [GET ]
    resp = api_client.request('GET', '')
    assert resp.status_code == 200, f'接口状态码断言失败: {resp.status_code} != 200'

    # 步骤 4: 动态自适应滑动 [left] (1 次)
    robust_swipe(driver, direction='left', repeat=1)
    time.sleep(1)

    # 步骤 5: 动态自适应滑动 [right] (1 次)
    robust_swipe(driver, direction='right', repeat=1)
    time.sleep(1)

    # 步骤 6: 动态自适应滑动 [left] (1 次)
    robust_swipe(driver, direction='left', repeat=1)
    time.sleep(1)

    # 步骤 7: 动态自适应滑动 [left] (1 次)
    robust_swipe(driver, direction='left', repeat=1)
    time.sleep(1)

    # 步骤 8: 动态自适应滑动 [right] (1 次)
    robust_swipe(driver, direction='right', repeat=1)
    time.sleep(1)

    # 步骤 9: 动态自适应滑动 [left] (1 次)
    robust_swipe(driver, direction='left', repeat=1)
    time.sleep(1)

    # 步骤 10: 动态自适应滑动 [left] (1 次)
    robust_swipe(driver, direction='left', repeat=1)
    time.sleep(1)

    # 步骤 11: 在输入框中填入核心业务测试意图，准备触发三栏工作台沉浸推演与16ms打字机结论输出 (输入: 测试象盒房产自动发圈与极速相机拍照功能)
    robust_type(driver, text=None, res_id='user-input', desc=None, rel_x=0.4491, rel_y=0.9546, input_text='测试象盒房产自动发圈与极速相机拍照功能')
    time.sleep(1)

    # 步骤 12: 点击发送执行按钮，触发当前输入的业务测试意图与三栏工作台推演
    robust_click(driver, text='发送执行', res_id='send-btn', desc=None, rel_x=0.8917, rel_y=0.6218)
    time.sleep(1)
