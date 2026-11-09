# Autotest 优化任务清单（交接给 Claude Code）

> 来源：2026-11-04 项目梳理。按顺序执行；每完成一项跑 `pytest` 验证并按 GEMINI.md 规范提交 commit（Conventional Commits）。遵守"最小改动"原则。

## P0-1 固化脚本无效（最高优先级）
- `web/app.py` ~1378/1385：终态断言用 `goal[:8]` / `goal[:12]`（用户意图文本）去 `page_source` 里找，必然失败。
  → 改为使用执行中实际观察到的页面关键文字（Verifier 最终确认的文本 / 最后一次 UI 树中的稳定文本，如底部 Tab 名）。取不到就不生成断言并在元数据中标记"缺少断言"。
- `web/app.py` ~1366：未提取到动作时退化为只有 `wait` + 假断言 → 改为拒绝固化并返回明确错误。
- `web/app.py` ~1340 tap 提取只保留坐标，丢弃了目标文字 → locator 带上 text（target_name）/resource-id，坐标作兜底。
- `ai_engine/solidifier.py` ~227 等处把字符串直接拼进 `'...'` → 全部改用 `repr()`，防止引号导致语法错误/代码注入。
- 新增测试：对生成脚本 `ast.parse` 校验；含单引号文本的用例；无动作时拒绝固化。
- 参考坏样本：`tests/solidified/象盒找房_4.9.12/test_auth_20261103_202630.py`

## P0-2 安全：局域网可远程执行代码 / 读文件
- `start_web.bat` 与 README：`--host 0.0.0.0` → 默认 `127.0.0.1`。
- `GET /api/solidified_cases/content`（query 版）未过滤路径，可 `filename=../../.env` 读密钥。
- `POST /api/run_pytest` filename 未过滤；配合 `POST /api/solidified_cases/save` 可写入并执行任意代码。
- 统一实现 `safe_path(base_dir, name)`：resolve 后必须位于 base_dir 内，否则 400；所有文件名参数接口都用它（content/delete/save/run_pytest/reports/uploads/apps）。
- 新增路径穿越安全测试。

## P0-3 会话持久化非原子
- `core/task_manager.py` `_save_session`：加每会话锁；先 `copy.deepcopy` 再写 `.tmp`，最后 `os.replace`。

## P1
4. `async def` 中的阻塞 `subprocess.run`/`time.sleep`（install、run_pytest、replay_deliverable、get_env_status 等）→ `asyncio.to_thread` 或改为普通 `def`。
5. 移除隐式 mock 兜底：`task_manager.py` ~3156、~3432 的 `["mock_device"]` → 无设备时直接报错（与"真机优先"原则一致）。
6. 拆分 `core/task_manager.py`（3539 行）与 `web/app.py`（80 个接口 → APIRouter 分文件）。先确认旧链路 `/api/plan/*`、`/api/run_real_test`、`CURRENT_PLAN_SESSION` 是否仍被前端使用，未使用则删除。
7. test_agent 中 39 处固定 sleep → 改为"等待 UI 树稳定"轮询。
8. 收窄 `except Exception: pass`，至少记日志。
9. `core/antigravity_oauth.py:29` 写死 `F:\PM-product\...` 路径 → 移到环境变量。（另：Antigravity 复用 IDE 的 OAuth client 调用内部接口，有合规/稳定性风险，不宜作为主通道。）

## P2
10. requirements.txt 补齐：fastapi、uvicorn、python-multipart、pytest-html、pypinyin、numpy、opencv-python；README 固定 Python 版本。
11. 清理：`scripts/` 下一次性 apply_*/patch_* 脚本、`web/templates/index.html.bak`、3 个 prototype_*.html（确认无用后）、根目录截图。
12. `index.html`（915KB）拆出 CSS/JS 到 static。
13. `tests/test_engine.py` 网络失败时伪造数据再断言 → 改为 skip 或 mock 请求。
14. `data/reports`、`data/sessions` 加保留策略。
