# 🤖 Autotest AI - 移动端全自动化测试与用例固化工作台

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Web-FastAPI%20%2B%20Bootstrap5-009688.svg)](https://fastapi.tiangolo.com/)
[![ADB Driver](https://img.shields.io/badge/Driver-Native%20ADB%20Speed-success.svg)](https://developer.android.com/tools/adb)
[![Zero Token Regression](https://img.shields.io/badge/Solidified-Zero%20Token%20Replay-orange.svg)](tests/solidified/)

**Autotest AI** 是一套面向移动端应用（Android / iOS）的**全智能自动化测试与确定性脚本固化工作台**。融合大语言模型（DeepSeek、Gemini / Antigravity、Claude、OpenAI 等）与原生 ADB 极速真机驱动，实现**“自然语言意图驱动 ➔ 多模态真机全自动测试 ➔ 智能自然语言问答式诊断 ➔ 零 Token 确定性 Python 脚本一键固化”**的全链路闭环。

---

## 🌟 核心特性与架构亮点

### 1. 🖥️ 桌面级 Web 交互工作台
- **现代化极简三栏布局**：
  - **左侧会话区**：历史测试任务持久化归档，进行中任务带有**实时动态转圈指示灯**，支持单任务检索与删除；
  - **中央对话流**：基于自然语言的沉浸式测试流，支持**任务规划推理（Thought）折叠展开**与**多阶段节点执行跟踪**；
  - **右侧工作台（Canvas）**：默认优雅折叠，专注提供**【全量日志】实时终端控制台**与**【屏幕显示】真机实时投屏镜像**（原来的交付物与脚本已被主界面独立的本地用例看板与对话流全面承接替代）。
- **双模工作台无缝切换**：
  - **AI 测试模式**：自然语言意图驱动、实时设备调度与多轮意图纠偏；
  - **本地用例看板**：已固化自动化资产集中管理，支持分类检索、一键 AI 复用与本地毫秒级直接回放。

### 2. ⚡ 纯真机原生 ADB 极速引擎（坚决杜绝免机仿真）
- **真机实测绝对优先（杜绝仿真）**：全面拥抱真实端侧体验，内置纯真机在线检测硬拦截，未连真机或设备离线（`device offline`）时**禁止盲测并拒绝建任务，坚决剔除任何隐式 Mock 降级**；
- **待测包强拦截（Pre-flight Check）**：应用安装失败或真机未就绪时立即以非零状态码阻断退出，**彻底杜绝“应用未装上却继续执行后续测试”的假跑现象**；
- **原生 ADB 极速驱动**：利用原生 ADB 管道直连真机，彻底免疫系统安装弹窗与权限拦截；
- **即插即用自动巡检**：多设备矩阵并发支持，精准感知 USB 连线状态与设备离线健康检查。

### 3. 🧠 设备画像自动识别与故障自进化知识库（Self-Learning）
- **毫秒级设备指纹提取**：
  - 自动识别已连接真机的硬件品牌（Xiaomi、Huawei、vivo、OPPO 等）、具体型号（如 MIX 2）、系统版本（Android 9/14）及 ROM 定制层（MIUI / HyperOS / OriginOS / ColorOS）；
- **优先查库，秒级复用（Cache-First）**：
  - 本地维护设备故障知识库（`data/device_knowledge.json`），若遇到已有记录（如小米手机必须开启【USB 调试（安全设置）】以授予 `INJECT_EVENTS` 模拟点击权限），**0 秒 0 Token 直接输出精准排查指南**；
- **未知故障 AI 自动推演与知识存盘（Self-Learning）**：
  - 当遇到全新机型或未记录的触控死锁时，系统自动提取底层 Logcat 日志片段，交由后台大模型进行根因分析与解法推演，**并将新规则自动持久化存盘追加到本地知识库**，实现设备自适应进化闭环；
- **前置手势注入安全探针**：
  - 驱动激活前向真机执行微秒级触控探针，若检测到系统拦截（`INJECT_EVENTS` denied），在第 0 步即刻阻断并给出图文排障指引，杜绝盲目消耗 15 步 AI Token。

### 4. 💬 单任务多轮连续对话、纠偏与独立停止按钮
- 支持在**同一条测试任务中进行连续自然对话**；
- 测试推进过程中可随时发送接续指令、纠偏指令或补充测试目标，系统自动在当前上下文内追加步骤流转，**无需频繁新建会话**；
- **独立黑色方块停止按钮 (Stop Button)**：
  - **原发送按钮**：黑色向上箭头（`bi-arrow-up`）保持原有样式与交互逻辑 100% 不变；
  - **独立停止按钮**：在发送按钮旁边新增独立的圆形底座 + **居中黑色实心小方块**；
  - **运行态呈现**：仅在测试任务处于运行中（RUNNING）时呈现，点击立即通过 Windows 系统级进程树递归强制终结命令（`taskkill /F /T /PID`）杀绝底层执行进程与 ADB 管道，**彻底杜绝日志继续滚动的现象，画面与动作瞬间停下**；
  - **空闲态自愈**：任务停止后自动隐藏，保持输入区极致清爽。

### 5. ✍️ 智能打字机效应与问答式自然结论
- **像大模型聊天回答一样输出**：摒弃繁重死板的边框卡片，以自然对话口吻直接输出测试结论；
  - **测试通过**：清晰归纳各阶段耗时、验证通过链路与固化脚本说明；
  - **测试受阻**：明确标出已通过步骤、当前卡点位置、阻断深度原因与排错建议；
- **智能打字机效应（Typewriter Effect）**：
  - 仅在测试任务**首次实时完成产出结论**时，以 16ms 节奏逐字流出并伴随闪烁光标；
  - 页面刷新（F5）、重新加载或切换查看历史任务时，**自动静默全量呈现，绝不重复打字**；
- **轻量内嵌直达文字链**：结论末尾提供极简直达链，一键呼出右侧工作台查看脚本源码或失败现场报告。

### 6. 🎯 待测应用胶囊与动态智能用例推荐
- 输入框底栏新增【待测应用胶囊】，自动联动扫描 `apps/` 目录下的 APK 安装包，支持一键切换并实时核验真机安装状态；
- 主界面空状态下动态根据所选待测包生成智能推荐业务用例网格（P0 核心流程、字段必填校验、全屏画廊轮播等）；
- 支持 **🔄 换一批** 实时刷新不同业务场景用例，点击卡片即可一键填充并启动测试。

### 7. 💡 全屏聚光灯新手 4 步向导
- 为新用户提供全屏高亮聚光灯指引：
  1. **第一步：确认物理真机在线（杜绝仿真）**：告知必须通过 USB 数据线连接手机并开启 USB 调试；
  2. **第二步：选定待测应用**：选择待测安装包与包名；
  3. **第三步：选择 AI 推理模型**：支持 Hermes / Antigravity / DeepSeek 任意点选；
  4. **第四步：输入业务意图并发送**：按 Enter 发送并实时观测推演流；
- 完成向导后弹出就绪卡片，可在顶部顶栏随时再次呼出复习。

### 8. 🛡️ 零 Token 确定性脚本固化（Solidification）
- 测试通过后，动作追踪器将操作时序自动编译固化为纯 Python 原生回归脚本（存放在 `tests/solidified/` 目录下）；
- 后续可脱离大模型调用，以**零 Token、零延迟、100% 确定性**直接用于 CI/CD 与高频冒烟回归。

---

## 📁 项目目录结构

```text
f:\Autotest
├── apps/                        # 待测安装包目录 (自动发现 APK / IPA)
├── config/
│   ├── settings.py              # 全局路径、设备超时与端口配置
│   └── ai_config.py             # 多大模型厂商接入 (DeepSeek / Gemini / Claude / OpenAI)
├── core/
│   ├── app_manager.py           # 原生应用生命周期与包管理
│   ├── device_knowledge_manager.py # 🌟 设备画像识别与故障自进化知识库管理器
│   ├── native_adb_driver.py     # 原生 ADB 极速真机驱动引擎 (含手势探针)
│   ├── task_manager.py          # 任务调度中心、步骤流水线与多会话状态机
│   └── llm_client.py            # 大模型统一网关与结构化推理
├── ai_engine/
│   ├── screen_parser.py         # 视觉截屏与 OCR 感知
│   ├── action_executor.py       # 原子动作执行器 (点击/滑动/输入/断言)
│   ├── test_agent.py            # AI 测试智能体核心循环 (含防死锁与自学习诊断)
│   └── solidifier.py            # 动作轨迹一键固化编译引擎
├── data/
│   ├── device_knowledge.json    # 🌟 持久化设备特征与机型避坑规则知识库
│   └── sessions/                # 历史测试会话与诊断日志 JSON 存储
├── tests/
│   ├── solidified/              # 固化生成的标准自动化测试脚本 (.py)
│   └── test_engine.py           # 基础驱动自检单元测试
├── web/
│   ├── app.py                   # FastAPI 后端服务与 RESTful 接口
│   ├── static/                  # 静态资源 (CSS / JS / 依赖库)
│   └── templates/
│       └── index.html           # 桌面级 Web 交互工作台前端单页
├── start_web.bat                # Web 端一键启动脚本 (Windows)
├── requirements.txt             # Python 依赖清单
└── README.md                    # 项目说明文档
```

---

## 🚀 极速上手指引

### 1. 环境准备
确保本机已安装：
- **Python 3.10+**
- **Android SDK Platform-Tools (ADB)**：确保终端执行 `adb devices` 能够正常输出设备列表。

安装 Python 依赖：
```bash
pip install -r requirements.txt
```

### 2. 物理真机准备（杜绝免机仿真）
1. 用 USB 数据线将 Android 手机连接至电脑；
2. 在手机中开启【开发者选项】➔【USB 调试】；
3. **国产定制机型重要提示**：
   - **小米/红米（MIUI / HyperOS）**：务必开启【USB 调试（安全设置）】，否则系统将拦截手势模拟点击（`INJECT_EVENTS` 权限）；
   - **vivo/iQOO（OriginOS）**：开启【USB 模拟点击】；
   - **OPPO/一加（ColorOS）**：开启【禁止权限监控】；
   - **华为（HarmonyOS）**：退出【纯净模式】。

### 3. 一键启动 Web 工作台
双击根目录下的 `start_web.bat`，或在命令行运行：
```bash
python -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
```
在浏览器中打开：`http://127.0.0.1:8000` 即可开始使用。
