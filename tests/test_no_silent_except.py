# -*- coding: utf-8 -*-
"""P1-8 守卫：业务代码中不得出现静默吞掉宽泛异常的 `except Exception: pass`"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("core", "ai_engine", "web", "config")
BROAD = {"Exception", "BaseException"}


def test_no_silent_broad_except_pass():
    offenders = []
    for d in SOURCE_DIRS:
        for path in (ROOT / d).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for h in ast.walk(tree):
                if not isinstance(h, ast.ExceptHandler):
                    continue
                broad = h.type is None or ast.unparse(h.type) in BROAD
                silent = len(h.body) == 1 and isinstance(h.body[0], ast.Pass)
                if broad and silent:
                    offenders.append(f"{path.relative_to(ROOT)}:{h.lineno}")
    assert not offenders, f"请至少记录日志（logger.debug(..., exc_info=True)）或收窄异常类型: {offenders}"
