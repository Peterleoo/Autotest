# -*- coding: utf-8 -*-
"""TaskManager 各 mixin 共享的数据目录常量"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SESSIONS_STORE_DIR = BASE_DIR / "data" / "sessions"
SESSIONS_STORE_DIR.mkdir(parents=True, exist_ok=True)
TEST_SUITES_STORE_DIR = BASE_DIR / "data" / "test_suites"
TEST_SUITES_STORE_DIR.mkdir(parents=True, exist_ok=True)
