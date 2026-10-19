# AI 移动端跨平台自动化测试与脚本固化引擎 (Autotest)

本项目基于 **GitHub 开源生态**（Appium 2.x、Pytest、Requests、Allure）以及 **多模态 AI 智能体技术**（借鉴腾讯 AppAgent 与字节 Midscene.js 的设计精髓），实现**Android（安卓）与 iOS（苹果）应用**的无死板工作流自动化测试。

---

## 🌟 核心特色与两阶段设计

1. **前期：AI 自由驱动测试（零门槛，无特定繁重工作流）**
   - 告别传统硬编码编写大量 Page Object 和繁琐 Locator 的沉重负担。
   - 用户只需提供一句自然语言意图（例如：*“安装并打开应用，测试输入错误账号密码的交互提示，并验证后端鉴权接口返回”*）。
   - AI 结合**屏幕截图（多模态视觉）**与**控件树**，自主规划并执行：应用安装 ➔ 点击/输入/滑动 ➔ 接口请求 ➔ 智能断言。

2. **后期：一键测试用例固化（Solidification）**
   - AI 探索与验证成功后，无侵入式轨迹追踪器会自动记录所有高价值动作。
   - **一键固化为标准、确定性的 Python (Pytest + Appium + Requests) 原生脚本**，存放于 `tests/solidified/`。
   - 固化后的用例可直接用于日常回归测试与 CI/CD 流水线，**零 Token 消耗、秒级高速执行、100% 确定性**。

3. **全维度测试覆盖**：
   - 📦 **应用安装与生命周期**：自动扫描 `apps/` 目录并完成 APK / IPA 安装与权限授予。
   - 🌐 **接口测试（API Testing）**：统一 Session、Token 传递、数据前后置准备与业务字段校验。
   - 📱 **功能与业务测试**：端到端业务主链路（登录注册、商品浏览、表单提交等）。
   - 👆 **交互体验测试**：点击、长按、滑动滚动、软键盘输入、弹窗自动放行、文案可见性断言。

4. **多模型生态支持**：
   - 支持 **Antigravity / Gemini 授权**接入
   - 支持 **DeepSeek**（DeepSeek-V3 / DeepSeek-R1）
   - 支持 **Claude / Anthropic**（系统已就绪）
   - 支持任意 **OpenAI 兼容协议**（本地 Ollama / vLLM / 通义千问等）

---

## 📁 目录结构

```
f:\Autotest
├── apps/                   # 存放待测安装包 (.apk / .ipa)
├── config/
│   ├── settings.py         # 平台、设备、Appium Server 与接口 Base URL 配置
│   └── ai_config.py        # 多模型厂商接入配置 (DeepSeek, Claude, Antigravity, OpenAI)
├── core/
│   ├── app_manager.py      # 应用安装、卸载、更新与设备生命周期管理
│   ├── driver_factory.py   # Appium 驱动管理工厂 (Android UiAutomator2 / iOS XCUITest)
│   ├── api_client.py       # 统一接口测试客户端 (会话、请求历史与断言)
│   └── llm_client.py       # 统一多模型调用与结构化决策层
├── ai_engine/
│   ├── screen_parser.py    # 屏幕截屏与控件树紧凑视图解析
│   ├── action_executor.py  # 原子操作执行器 (Tap, Type, Swipe, API, Assert) 与动作追踪
│   ├── test_agent.py       # AI 智能探索与测试决策主循环
│   └── solidifier.py       # 核心：测试动作轨迹一键固化编译引擎
├── tests/
│   ├── solidified/         # 存放 AI 跑通后自动固化生成的确定性测试脚本 (如 test_login.py)
│   └── test_engine.py      # 引擎能力自检测试
├── .env.example            # 环境变量配置模板
├── pytest.ini              # Pytest 运行配置
├── requirements.txt        # Python 依赖清单
└── run_ai_test.py          # AI 驱动测试与固化入口 CLI
```

---

## 🚀 快速上手与使用指引

### 1. 放入待测应用
将您的测试安装包直接拷贝到 `apps/` 目录下（例如 `apps/my_app.apk`）。
程序在启动时会自动发现并执行安装与授权。

### 2. 配置模型（任选其一）
复制 `.env.example` 为 `.env`，根据需要配置对应的 AI Key：
```env
# 启用模型类型: deepseek / claude / antigravity / openai
AI_PROVIDER=deepseek

# 若使用 DeepSeek:
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 若使用 Claude (系统环境变量已默认支持):
# AI_PROVIDER=claude

# 若使用 Antigravity / Gemini:
# AI_PROVIDER=antigravity
# ANTIGRAVITY_API_KEY=your_gemini_key
```

### 3. 跨平台运行配置

#### A. 安卓（Android - Windows 本地运行）
1. 连接 Android 真机（开启 USB 调试）或启动 Android 模拟器。
2. 在终端启动 Appium 服务：
   ```bash
   appium
   ```
3. 检查设备连接：
   ```bash
   adb devices
   ```

#### B. 苹果（iOS - 局域网 macOS 机器支持）
1. 在局域网内的 Mac 机器上启动 Appium 服务（监听 `0.0.0.0:4723`）：
   ```bash
   appium --address 0.0.0.0 --port 4723
   ```
2. 在 Windows 的 `.env` 中指定 Mac 的局域网 IP：
   ```env
   TARGET_PLATFORM=ios
   APPIUM_SERVER_URL=http://192.168.1.100:4723
   IOS_DEVICE_NAME=iPhone 15
   IOS_BUNDLE_ID=com.example.yourapp
   ```

---

### 4. 运行 AI 自动化测试与自动固化

只需执行统一入口 `run_ai_test.py`，并输入自然语言意图：

```bash
# 示例 1: 登录与注册测试并固化为 test_login_register.py
python run_ai_test.py -g "打开应用，测试账号密码登录流程，若有用户协议先点击同意，并调用登录鉴权接口验证" -n "login_register"

# 示例 2: 核心业务流程测试
python run_ai_test.py -g "进入应用首页，搜索商品'手机'，点击第一项加入购物车，并断言页面出现成功提示" -n "business_order_flow"
```

- AI 将自动接管手机屏幕，完成交互并验证接口。
- 测试完成后，系统自动在 `tests/solidified/` 目录下生成同名的原生 Python 测试脚本。

---

### 5. 执行固化脚本与查看测试报告（零 AI 消耗）

后期进行日常批量回归测试时，直接通过 Pytest 执行固化脚本：

```bash
# 执行所有固化生成的测试用例
pytest tests/solidified/ -v -s

# 执行生成 Allure 可视化测试报告
pytest tests/solidified/ --alluredir=reports/allure_results
allure serve reports/allure_results
```
