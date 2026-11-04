# -*- coding: utf-8 -*-
"""P1-4 守卫：async 接口内不得直接调用阻塞 API（会卡死整个事件循环）"""
import ast
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
WEB_FILES = [WEB_DIR / "app.py", WEB_DIR / "shared.py", *sorted((WEB_DIR / "routers").glob("*.py"))]
BLOCKING = {
    ("subprocess", "run"), ("subprocess", "check_output"), ("subprocess", "call"),
    ("subprocess", "check_call"), ("time", "sleep"), ("request", "urlopen"),
    ("requests", "get"), ("requests", "post"),
}


def _blocking_calls(node, inside_lambda=False):
    """递归查找阻塞调用；lambda 内的调用视为已交给 asyncio.to_thread，嵌套函数单独判定"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        in_lambda = inside_lambda or isinstance(child, ast.Lambda)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and not in_lambda:
            base = child.func.value
            base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
            if (base_name, child.func.attr) in BLOCKING:
                yield f"{base_name}.{child.func.attr} @ line {child.lineno}"
        yield from _blocking_calls(child, in_lambda)


def test_async_endpoints_do_not_call_blocking_apis_directly():
    offenders = {}
    for path in WEB_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if isinstance(fn, ast.AsyncFunctionDef):
                offenders[f"{path.name}:{fn.name}"] = list(_blocking_calls(fn))
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, f"async 函数中存在阻塞调用，请改为 def 或 asyncio.to_thread: {offenders}"
