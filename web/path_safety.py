# -*- coding: utf-8 -*-
"""文件名参数的路径穿越防护"""
from pathlib import Path

from fastapi import HTTPException


def safe_path(base_dir: Path, name: str) -> Path:
    """
    将用户提供的文件名解析为 base_dir 内的真实路径。
    resolve 后不在 base_dir 内（含 ..、绝对路径、盘符、符号链接逃逸）一律 400。
    """
    if not isinstance(name, str) or not name.strip() or "\x00" in name:
        raise HTTPException(status_code=400, detail="非法文件名")
    base = Path(base_dir).resolve()
    target = (base / name).resolve()
    if target == base or base not in target.parents:
        raise HTTPException(status_code=400, detail="非法文件名")
    return target
