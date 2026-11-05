# -*- coding: utf-8 -*-
"""TaskManager 各 mixin 共享的数据目录常量

AUTOTEST_SESSIONS_DIR / AUTOTEST_TEST_SUITES_DIR 可覆盖默认目录：
自动化测试 (tests/conftest.py) 借此把会话写入临时目录，避免污染用户任务列表；
环境变量会被 run_ai_test.py 等子进程继承，保证父子进程读写同一目录。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_STORE_DIR = Path(os.environ.get("AUTOTEST_SESSIONS_DIR") or BASE_DIR / "data" / "sessions")
SESSIONS_STORE_DIR.mkdir(parents=True, exist_ok=True)
TEST_SUITES_STORE_DIR = Path(os.environ.get("AUTOTEST_TEST_SUITES_DIR") or BASE_DIR / "data" / "test_suites")
TEST_SUITES_STORE_DIR.mkdir(parents=True, exist_ok=True)
