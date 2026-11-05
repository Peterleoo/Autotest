# 🤖 Autotest AI - 移动端全自动化测试与用例固化工作台

[![Python Version](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
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

### 9. ⚖️ 借鉴 DeepSeek Harness (DSH) 的三权分立与假阳性防护门禁
- **独立任务核验门禁（TaskVerifier Gate）**：
  - 剥夺执行大模型（LLM）既当执行者又当裁判的权力，建立独立审查门禁（`TaskVerifier`）；
  - 当大模型在未跳出登录/注册页面、或未进入目标业务页面就试图调用 `finish` 并声称“验证了权限拦截逻辑正常”时，门禁予以**一票否决**，强制注入警示并促使自愈，彻底杜绝虚假达成（False Positive）；
- **真实凭证物理注入流水线（Credential Injection Pipeline）**：
  - 遇到登录鉴权阻断且配置了测试凭证时，系统自动执行真实输入：OCR 精准定位账号/密码框、物理键入凭证、智能勾选协议单选框并提交，核验真机真实跳出登录页后继续执行；
- **动态任务突变与自愈插桩（Plan Mutation）**：
  - 执行中感知到鉴权阻断时，任务中心在当前步骤后即时插桩 `[动态自愈] 自动注入测试凭证完成登录放行`（标注 `diff_type: "added"`），并在前端 TodoList 以动效流式呈现自愈全貌；
- **终态核心断言守卫（Assertion Guard）**：
  - 若原任务中带有“验证/断言/核验/成功弹出”等核心断言步骤被跳过（SKIPPED），系统坚决拒绝草率判定为通过，如实定性为 `BLOCKED`（业务受阻 / 待补前置），前端以高质感琥珀金胶囊条清晰展示。

### 10. 📑 需求驱动用例智能生成与自由编排系统 (Suite Builder)
- **文档一键智能提炼（Spec Synthesis）**：
  - 支持直接上传产品需求文档（PRD/Word `.docx`、PDF、Markdown、纯文本 `.txt`）；
  - 后端智能提取核心业务规则并交由 `TestSpecSynthesizer` 提炼为强类型用例套件（TestSuite，含模块划分、优先级 P0/P1/P2、核心目标与关键断言规则）；
- **Generative UI 自由编排卡片**：
  - 遵循现代工程级极简设计范式，在时间线中原地渲染可交互套件编排卡片；
  - 支持原地双击即时编辑用例标题/测试目标、自由勾选组合、上下调换执行顺序、单项删除与一键增补自定义用例；
- **系统级现场串联执行（Systemic Suite Execution with State Retention）**：
  - 支持一键发起系统级测试，开启“保持应用现场连续探索（`keep_state: true`）”；
  - 真机按编排时序无缝串联执行各用例，用例间不杀进程、继承登录态与界面上下文；
  - 执行完成后自动聚合成系统级全景测试报告，并将调优后的用例套件持久化存盘至 `data/test_suites/` 供未来秒级直接复跑。

### 11. 🛡️ 需求文档与待测应用相关性校验门禁 (Doc Mismatch Guard)
- **业务领域语义比对**：
  - 当用户上传文档并发起测试时，门禁自动提取文档核心关键词与当前待测 APK/应用元数据进行交叉比对；
  - 若检测到文档与当前待测应用无关（例如在房产或外卖 App 上传了外语教学课件），系统进行**智能前置阻断**；
- **自愈式 Generative UI 告警交互**：
  - 在时间线呈现优雅警示卡片，清晰说明不匹配原因，并提供“重新确认/修改意图”与“仍要强制执行”双向选择，从源头杜绝盲目消耗 Token 与无效测试。

### 12. ⚡ 分层感知三级火箭架构 (Layered Perception Architecture)
- **Level 1 (UI 树极速短路)**：
  - 若真机 UIAutomator 原生控件树信息充沛（富含文本、ID、清晰控件层级），感知层自动短路，跳过全量大图截屏与图片网络上传；
  - 采用结构化纯文本毫秒级直接决策，单步决策耗时从 5~8 秒直降至 **400~800ms**，Token 消耗节省超 **80%**；
- **Level 2 (端侧本地 OCR 补齐兜底)**：
  - 当页面为自绘 Webview / Flutter / H5 等导致原生 UI 树节点稀疏时，自动激活端侧轻量 OCR 补齐文字位置并以轻量文本决策；
- **Level 3 (视觉多模态大模型攻坚)**：
  - 仅在纯图标按钮、复杂图形滑块验证码或遇到阻断重试时，无缝升格为全量截屏 + 多模态视觉模型（Vision）攻坚，确保 100% 视觉兜底与稳定性。

### 13. 🤝 人机协同挂起与连续对话意图拦截中枢 (HITL & Intent Gate)
- **人机协同挂起（Human-in-the-Loop, HITL）**：
  - 遇到短信验证码、生物识别或人工强校验场景，测试智能体优雅挂起，在前端渲染倒计时人机协同卡片；
  - 用户可在卡片中直接填入验证码放行，或一键点击取消终止；
- **控制意图拦截中枢 (Intent Gate)**：
  - 彻底重构多轮对话入口，建立控制指令正则与模式识别；
  - 当任务处于等待或执行态时，用户在底部输入框输入“停止”、“终止”、“取消”、“退出”等词汇，系统第一时间拦截并优雅中止底层进程，坚决不将其误识别为追加测试业务步骤；
- **无重复流式渲染与 DOM 脏检查**：
  - 全面消除前端临时乐观节点与后端权威 Block 的冲突，通过 DOM 脏检查机制杜绝重复消息气泡与页面闪烁。

### 14. 🧱 统一时间线标准事件流 (借鉴 Vercel Labs json-render 契约护栏)
- **权威组件 Catalog 白名单**：
  - 依托 `TimelineManager` 建立受控的强类型 Block 契约（`user_message`, `system_notice`, `thought`, `todo_list`, `step_execution`, `suite_builder`, `doc_mismatch_guard`, `test_summary`, `fault_diagnosis`, `report`）；
  - 任何非规范数据结构自动安全降级，前端与后端数据契约严丝合缝，杜绝未知类型导致界面白屏。

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
│   ├── task_manager.py          # 任务调度中心、DSH 计划突变与断言守卫
│   ├── test_spec_synthesizer.py # 🌟 需求文档驱动用例套件智能提取与编排引擎 (Suite Builder)
│   ├── timeline_manager.py      # 🌟 标准化时间线 Block 契约管理器 (json-render catalog)
│   └── llm_client.py            # 大模型统一网关与结构化推理
├── ai_engine/
│   ├── verifier.py              # 🌟 独立核验门禁与反幻觉审查 (TaskVerifier Gate)
│   ├── screen_parser.py         # 视觉截屏与 OCR 感知 (含分层感知评估)
│   ├── action_executor.py       # 原子动作执行器 (点击/滑动/输入/断言)
│   ├── test_agent.py            # AI 测试智能体核心循环 (含分层感知调度与门禁审查)
│   └── solidifier.py            # 动作轨迹一键固化编译引擎
├── data/
│   ├── device_knowledge.json    # 🌟 持久化设备特征与机型避坑规则知识库
│   ├── test_suites/             # 🌟 持久化系统级测试用例套件存储库
│   └── sessions/                # 历史测试会话与诊断日志 JSON 存储
├── tests/
│   ├── test_dsh_verifier_and_injection.py # 🌟 DSH 独立门禁与凭证注入机制单元测试
│   ├── test_test_spec_synthesizer.py      # 🌟 用例套件合成与系统级串联测试套件
│   ├── test_timeline_schema_contract.py   # 🌟 时间线强类型契约校验测试
│   ├── test_layered_perception.py         # 🌟 分层感知三级火箭分流单元测试
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
- **Python 3.14**（当前开发与测试所用版本；代码语法兼容 3.10+，但未在旧版本上实测）
- **Android SDK Platform-Tools (ADB)**：确保终端执行 `adb devices` 能够正常输出设备列表。

安装 Python 依赖：
```bash
pip install -r requirements.txt
python -m playwright install chromium   # 仅运行前端 UI 测试时需要
```

### 2. 物理真机准备（杜绝免机仿真）
1. 用 USB 数据线将 Android 手机连接至电脑；
2. 在手机中开启【开发者选项】➔【USB 调试】；
3. **国产定制机型重要提示**：
   - **小米/红米（MIUI / HyperOS）**：务必开启【USB 调试（安全设置）】，否则系统将拦截手势模拟点击（`INJECT_EVENTS` 权限）；
   - **vivo/iQOO（OriginOS）**：开启【USB 模拟点击】；
   - **OPPO/一加（ColorOS）**：开启【禁止权限监控】；
   - **华为（HarmonyOS）**：退出【纯净模式】。

4. **投屏推流（推荐，显著降低真机耗电）**：执行 `python tools/fetch_scrcpy_server.py` 下载并校验 scrcpy-server（Apache-2.0），并确保已安装 `av`。就绪后投屏与 AI 取帧自动改用真机硬件 H.264 推流；未就绪时自动回退截屏。相关配置见 `.env.example` 中「投屏与真机取帧」一节。

### 3. 配置 AI 模型（以 Google Antigravity 为例）
每位部署者都使用**自己的** Google 账号与额度，凭据只保存在本机，绝不提交到仓库：

1. 复制配置模板：`cp .env.example .env`（`.env` 已被 git 忽略）；
2. 在 `.env` 中填写 `ANTIGRAVITY_CLIENT_ID` 与 `ANTIGRAVITY_CLIENT_SECRET`（Antigravity OAuth 客户端凭据，请自行获取，仓库不提供）；
3. 启动工作台后在界面中点击 **Antigravity 登录**，浏览器完成 Google 授权后，个人令牌会自动保存到本机 `config/antigravity_oauth.json`（已被 git 忽略，切勿分享）；
4. （可选）如需 OpenAI 兼容的本地桥接服务：`python tools/antigravity_bridge.py`
   - 默认只监听 `127.0.0.1:19387`，**不要改成 `0.0.0.0`**，否则局域网内任何人都能消耗你的模型额度；
   - 如需额外防护，在 `.env` 中设置 `ANTIGRAVITY_BRIDGE_KEY`，并让 `ANTIGRAVITY_API_KEY` 与之保持一致。

不使用 Antigravity 时，也可以在 `.env` 中改配 DeepSeek / Claude / OpenAI 等其他模型。

### 4. 一键启动 Web 工作台
双击根目录下的 `start_web.bat`，或在命令行运行：
```bash
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir core --reload-dir web --reload-dir ai_engine --reload-dir config
```
在浏览器中打开：`http://127.0.0.1:8000` 即可开始使用。
