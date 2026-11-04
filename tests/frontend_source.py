# -*- coding: utf-8 -*-
"""测试辅助：读取完整前端源码（index.html 骨架 + web/static 下的 CSS/JS）"""
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def read_frontend_source() -> str:
    parts = [(WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8")]
    for pattern in ("static/css/*.css", "static/js/*.js"):
        parts += [p.read_text(encoding="utf-8") for p in sorted(WEB_DIR.glob(pattern))]
    return "\n".join(parts)
