---
project_id: "Autotest"
project_name: "Autotest AI (移动端全自动化测试与用例固化工作台)"
workflow_mode: "B"
mode_name: "模式 B · 中型特性流"
current_focus: "refinement"
focus_name: "全景产品定义与基线梳理"
current_stage: "吸收重大工程落地升级，确立物理真机优先与七大护城河能力"
progress_percentage: 100
health_score: 100
health_level: "卓越 (Excellent)"
status: "active"
created_at: "2026-10-20"
updated_at: "2026-10-22"
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

---

## 三、 交付物全景注册表 (Deliverables Registry)

| 序号 | 交付物名称 | 所属业务焦点 | 物理文件路径 / 访问链接 | 交付日期 | 状态 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| + | Autotest AI 产品全景梳理与业务规格说明书 | 功能方案推进 (solution) | [Autotest AI 产品全景梳理与业务规格说明书](file:///F:/Autotest) | 2026-10-22 | 已交付 |
| + | 现有工程页面产品体验走查与对齐优化清单 | 功能方案推进 (solution) | [现有工程页面产品体验走查与对齐优化清单](file:///F:/Autotest) | 2026-10-22 | 已交付 |
| + | 非专业人员团队自测工作台轻量规格说明书 | 功能方案推进 (solution) | [非专业人员团队自测工作台轻量规格说明书](file:///F:/Autotest) | 2026-10-22 | 已交付 |
| + | Autotest 产品规划与路线图方案 (v1.1) | 功能方案推进 (solution) | [Autotest 产品规划与路线图方案 (v1.1)](file:///F:/Autotest) | 2026-10-22 | 已交付 |
| 1 | 初始项目工程骨架 | 基础 | [README.md](README.md) | 2026-10-20 | 已存在 |
| 2 | 产品规划与路线图方案 (v1.1) | roadmap | [docs/roadmap.md](docs/roadmap.md) | 2026-10-20 | 已验收 |
| 3 | 团队自测工作台功能规格说明 | spec | [specs/spec-team-self-test-console.md](specs/spec-team-self-test-console.md) | 2026-10-20 | 已验收 |
| 4 | 工程活原型体验走查与优化清单 | audit | [docs/engineering-page-audit.md](docs/engineering-page-audit.md) | 2026-10-20 | 已验收并指导研发 |
| 5 | **Autotest AI 产品全景梳理与业务规格** | definition | [docs/product-definition.md](docs/product-definition.md) | 2026-10-20 | **最新基准 (已落盘)** |

---

## 四、 关键产品决策日志 (Product Decision Log)

- **[2026-10-20] 重大战略合并：Now 与 Next 并轨推进**:
  - 用户明确指出产品本质是面向非专业测试人员团队自测，必须直接交付 Web UI 与协作闭环。
- **[2026-10-20] 坚决不输出孤立静态原型，以现有工程页面作为“活体原型”**:
  - 避免双轨脱节与资源浪费，直接输出 3 项高 ROI 体验优化清单并指导研发落地。
- **[2026-10-20] 吸收最新工程优化成果，重塑真机实测优先与 7 大核心能力**:
  - 确立“真机实测优先、坚决杜绝免机仿真”原则；
  - 固化手势探针硬拦截、设备画像自进化知识库、三栏桌面级工作台、单会话多轮纠偏、物理级一键强杀制动、用例推荐与新手向导等 7 大核心产品能力。

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
