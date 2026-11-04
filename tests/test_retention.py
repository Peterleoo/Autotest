# -*- coding: utf-8 -*-
"""P2-14 数据保留策略：过期清理、保留最新 N 个、跳过隐藏与写入中文件"""
import os
import time

from core.retention import prune_old_files, SECONDS_PER_DAY


def _make(path, age_days):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    ts = time.time() - age_days * SECONDS_PER_DAY
    os.utime(path, (ts, ts))
    return path


def test_deletes_only_files_older_than_cutoff(tmp_path):
    old = _make(tmp_path / "old.json", 100)
    fresh = _make(tmp_path / "fresh.json", 1)
    deleted = prune_old_files(tmp_path, max_age_days=90, keep_latest=0)
    assert deleted == [old]
    assert fresh.exists() and not old.exists()


def test_always_keeps_latest_n_even_if_expired(tmp_path):
    files = [_make(tmp_path / f"s{i}.json", 200 + i) for i in range(5)]
    prune_old_files(tmp_path, max_age_days=30, keep_latest=2)
    assert [f.exists() for f in files] == [True, True, False, False, False]


def test_disabled_and_skips_hidden_tmp_files(tmp_path):
    keep = _make(tmp_path / ".gitkeep", 999)
    tmp = _make(tmp_path / "a.json.tmp", 999)
    old = _make(tmp_path / "old.json", 999)
    assert prune_old_files(tmp_path, max_age_days=0, keep_latest=0) == []
    assert old.exists()
    prune_old_files(tmp_path, max_age_days=30, keep_latest=0)
    assert keep.exists() and tmp.exists() and not old.exists()


def test_recursive_covers_subdirectories(tmp_path):
    nested = _make(tmp_path / "markdown" / "r.md", 60)
    top = _make(tmp_path / "top.html", 60)
    assert prune_old_files(tmp_path, max_age_days=30, keep_latest=0) == [top]
    assert nested.exists()
    prune_old_files(tmp_path, max_age_days=30, keep_latest=0, recursive=True)
    assert not nested.exists()
