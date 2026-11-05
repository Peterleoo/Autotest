# -*- coding: utf-8 -*-
"""全局测试隔离：会话与用例套件写入临时目录，绝不污染用户真实任务列表 (data/sessions)

必须在任何 core.* 模块导入前设置环境变量；子进程 (run_ai_test.py 等) 会继承同一目录。
测试结束时不删除本次目录（后台线程可能仍在落盘），启动时清理一天前的历史目录。
"""
import os
import shutil
import tempfile
import time
from pathlib import Path

_PREFIX = "autotest_pytest_"
_STALE_SECONDS = 24 * 3600


def _purge_stale_dirs() -> None:
    for d in Path(tempfile.gettempdir()).glob(f"{_PREFIX}*"):
        try:
            if time.time() - d.stat().st_mtime > _STALE_SECONDS:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


_purge_stale_dirs()
_TEST_DATA_ROOT = Path(tempfile.mkdtemp(prefix=_PREFIX))
os.environ["AUTOTEST_SESSIONS_DIR"] = str(_TEST_DATA_ROOT / "sessions")
os.environ["AUTOTEST_TEST_SUITES_DIR"] = str(_TEST_DATA_ROOT / "test_suites")
