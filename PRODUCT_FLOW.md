---
project_id: "Autotest"
project_name: "Autotest AI (移动端全自动化测试与用例固化工作台)"
workflow_mode: "B"
mode_name: "模式 B · 中型特性流"
current_focus: "refinement"
focus_name: "全景产品定义与系统级架构演进"
current_stage: "吸收需求编排Suite Builder、分层感知火箭、HITL协同与时间线契约等重大工程升级"
progress_percentage: 100
health_score: 100
health_level: "卓越 (Excellent)"
status: "active"
created_at: "2026-10-20"
updated_at: "2026-11-04"
owner: "Product Manager"
---

# Autotest AI - ProductOS 流程与资产台账

> **核心定位**: 专为非专业测试人员（业务开发、PM、业务测试）打造的 **物理真机优先、多模态智能驱动与零 Token 原生脚本固化工作台**。  
> **工作流架构**: 【模式 B · 中型特性流】 ｜ 当前业务焦点：【全景产品定义与基线梳理】 (refinement)  
> **核心原则**: **真机实测优先，坚决杜绝免机仿真 (Real-Device-First, Zero-Mock Policy)**。

---

## 一、 产品边界与约束契约 (Boundaries & Constraints)
- **明确做什么 (In-Scope)**:
  - 核心闭环：意图输入 ➔ 极速预检（真机+手势探针）➔ 多模态真机驱动 ➔ 16ms 打字机人话结论 ➔ 单会话多轮纠偏 ➔ 一键固化原生 Pytest 脚本 ➔ CI/CD 秒级 0 Token 回归。
  - 三栏沉浸式桌面级工作台（会话历史、中央推演流与 Thought 折叠、右侧投屏/终端 Canvas）。
  - 设备自学习避坑知识库（Cache-First 秒级图文指引 + 自动沉淀）。
- **坚决不做什么 (Out-of-Scope / Non-Goals)**:
  - **坚决杜绝免机仿真与假跑**（必须物理真机实跑，确保线上真实质量）；
  - **坚决不造脱节的静态原型**（直接以 `web/templates/index.html` 活原型为准）；
  - 暂不引入重型分布式集群与复杂低代码拖拽；
  - 恪守产品经理职责：不越界输出具体后端微服务代码或数据库物理表 DDL。

---

## 二、 模式专属推进流水线 (Stage Milestones)

- [x] 1. 业务现状盘点与资产梳理
- [x] 2. 系统边界界定与核心痛点抽象
- [x] 3. 产品定位与路线图规划 (roadmap - Now与Next战略合并)
- [x] 4. 核心功能场景规格说明 (specs/spec-team-self-test-console.md)
- [x] 5. 交互原型与体验走查 (复用工程页面 web/templates/index.html，产出 docs/engineering-page-audit.md)
- [x] 6. 验收自检与用户确认评审 (用户正式确认采纳，研发团队已对接优化)
- [x] 7. 吸收工程调整成果，完成全景产品定义与基线重梳理 (docs/product-definition.md)
- [x] 8. 落地需求驱动用例智能生成与自由编排系统 (Suite Builder) 与现场上下文继承 (keep_state)
- [x] 9. 落地文档与应用语义相关性校验门禁 (Doc Mismatch Guard) 阻断无关盲测
- [x] 10. 落地分层感知三级火箭架构 (UI树极速短路 ➔ 本地OCR兜底 ➔ 视觉大模型攻坚)
- [x] 11. 落地 HITL 人机协同挂起、连续对话控制指令拦截中枢 (Intent Gate) 与标准化时间线 Block Catalog

---

## 三、 交付物全景注册表 (Deliverables Registry)

| 序号 | 交付物名称 | 所属业务焦点 | 物理文件路径 / 访问链接 | 交付日期 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| + | 需求驱动智能用例生成与自由编排套件 | 功能方案推进 (suite) | [core/test_spec_synthesizer.py](file:///F:/Autotest/core/test_spec_synthesizer.py) | 2026-10-31 | 已交付 |
| + | 分层感知三级火箭评估与分流器 | 引擎性能优化 (perception) | [ai_engine/screen_parser.py](file:///F:/Autotest/ai_engine/screen_parser.py) | 2026-11-01 | 已交付 |
| + | 统一时间线标准事件流管理器 (Catalog) | 架构规范推进 (timeline) | [core/timeline_manager.py](file:///F:/Autotest/core/timeline_manager.py) | 2026-11-03 | 已交付 |
| + | 控制指令意图拦截中枢 (Intent Gate) | 交互闭环 (hitl) | [core/task_manager.py](file:///F:/Autotest/core/task_manager.py) | 2026-11-02 | 已交付 |
| 1 | 初始项目工程骨架 | 基础 | [README.md](README.md) | 2026-10-20 | 已存在 |
| 2 | 产品规划与路线图方案 (v1.1) | roadmap | [docs/roadmap.md](docs/roadmap.md) | 2026-10-20 | 已验收 |
| 3 | 团队自测工作台功能规格说明 | spec | [specs/spec-team-self-test-console.md](specs/spec-team-self-test-console.md) | 2026-10-20 | 已验收 |
| 4 | 工程活原型体验走查与优化清单 | audit | [docs/engineering-page-audit.md](docs/engineering-page-audit.md) | 2026-10-20 | 已验收并指导研发 |
| 5 | **Autotest AI 产品全景梳理与业务规格** | definition | [docs/product-definition.md](docs/product-definition.md) | 2026-11-04 | **最新基准 (v2.5已落盘)** |

---

## 四、 关键产品决策日志 (Product Decision Log)

- **[2026-10-20] 重大战略合并：Now 与 Next 并轨推进**:
  - 用户明确指出产品本质是面向非专业测试人员团队自测，必须直接交付 Web UI 与协作闭环。
- **[2026-10-20] 坚决不输出孤立静态原型，以现有工程页面作为“活体原型”**:
  - 避免双轨脱节与资源浪费，直接输出 3 项高 ROI 体验优化清单并指导研发落地。
- **[2026-10-20] 吸收最新工程优化成果，重塑真机实测优先与 7 大核心能力**:
  - 确立“真机实测优先、坚决杜绝免机仿真”原则；
  - 固化手势探针硬拦截、设备画像自进化知识库、三栏桌面级工作台、单会话多轮纠偏、物理级一键强杀制动、用例推荐与新手向导等 7 大核心产品能力。
- **[2026-10-31] 落地 Suite Builder：从“单点单步”走向“系统级套件端到端探索”**:
  - 解决需求文档到测试执行的手工鸿沟，支持通过 Generative UI 进行用例自由重组、增删与原位修改；
  - 确立“用例间保持应用现场状态（`keep_state: true`）”，实现单次会话执行整套端到端业务流。
- **[2026-11-01] 构筑分层感知三级火箭架构，彻底破解高昂延迟与 Token 消耗**:
  - 确立“UIAutomator 丰富原生树优先毫秒级纯文本决策，自绘稀疏界面本地 OCR 兜底，复杂无字图形/阻断重试升级多模态 Vision”的三层分流机制。
- **[2026-11-02] 重塑交互中枢：意图拦截中枢 (Intent Gate) 与人机协同 (HITL)**:
  - 彻底终结把控制指令（“停止”、“终止”）误当测试业务 Prompt 的逻辑缺陷；
  - 解决前端双重乐观节点的脏渲染问题，实现 DOM 脏检查与防抖防闪烁。
- **[2026-11-03] 借鉴 Vercel Labs json-render 契约护栏，规范时间线事件流**:
  - 确立强类型 Block Catalog 白名单，杜绝未定义类型导致的界面渲染白屏与崩溃，双向兼容 `todo_list` 与 `todo_plan`。

---

## 五、 当前核心阻力与下一步行动 (Next Actions)
- **当前核心阻力/阻塞项**: 无（全景产品基线与最新工程成果已完全对齐）
- **下一步行动建议 (Recommended Next Action)**:
  - 👉 **向业务团队与测试用户正式发布全新产品定义与使用向导，基于真机环境验证 3 分钟极速自测闭环。**

---

## 六、 产品资产健康度与增量缺口诊断 (Asset Gap Analysis)

| 序号 | 严重级别 | 诊断项 | 现状说明 | 建议最小动作 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 🟢 卓越 | 产研完全闭环 | 工程页面调整与产品定义说明书 100% 对齐，具备极高交付水准 | 正式面向团队推广自测工作流 |
