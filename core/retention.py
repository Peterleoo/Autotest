# -*- coding: utf-8 -*-
"""数据保留策略：按修改时间清理过期的测试报告与会话文件"""
import logging
import time
from pathlib import Path
from typing import List

logger = logging.getLogger("Retention")

SECONDS_PER_DAY = 86400


def prune_old_files(directory: Path, max_age_days: int, keep_latest: int, recursive: bool = False) -> List[Path]:
    """
    删除 directory 下修改时间早于 max_age_days 天的文件，但始终保留最新的 keep_latest 个。
    max_age_days <= 0 时不清理；隐藏文件（如 .gitkeep）与 .tmp 写入中的文件不参与。
    返回被删除的文件列表。
    """
    if max_age_days <= 0 or not directory.is_dir():
        return []
    pattern = "**/*" if recursive else "*"
    files = [
        p for p in directory.glob(pattern)
        if p.is_file() and not p.name.startswith(".") and p.suffix != ".tmp"
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    cutoff = time.time() - max_age_days * SECONDS_PER_DAY

    deleted = []
    for path in files[max(0, keep_latest):]:
        if path.stat().st_mtime >= cutoff:
            continue
        try:
            path.unlink()
            deleted.append(path)
        except OSError as e:
            logger.warning(f"清理过期文件失败 {path}: {e}")
    if deleted:
        logger.info(f"🧹 数据保留策略：{directory} 清理 {len(deleted)} 个超过 {max_age_days} 天的文件")
    return deleted
