# -*- coding: utf-8 -*-
"""P0-3 会话持久化：原子写入、并发安全、重命名落盘"""
import asyncio
import json
import threading

import pytest

import core.task_manager as tm_module
from web.app import task_mgr, rename_session

SID = "sess_unit_p03_persist"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(tm_module, "SESSIONS_STORE_DIR", tmp_path)
    task_mgr.sessions[SID] = {"session_id": SID, "title": "原标题", "logs": []}
    yield tmp_path
    task_mgr.sessions.pop(SID, None)


def _read(store):
    return json.loads((store / f"{SID}.json").read_text(encoding="utf-8"))


def test_failed_write_keeps_previous_file_intact(store, monkeypatch):
    task_mgr._save_session(SID)
    assert _read(store)["title"] == "原标题"

    def broken_dump(obj, fp, **kwargs):
        fp.write('{"title": "半截')
        raise IOError("disk full")

    monkeypatch.setattr(tm_module.json, "dump", broken_dump)
    task_mgr.sessions[SID]["title"] = "新标题"
    task_mgr._save_session(SID)
    monkeypatch.undo()

    assert _read(store)["title"] == "原标题"
    assert not list(store.glob(f"{SID}*.tmp"))


def test_concurrent_mutation_and_saves_always_produce_valid_json(store, caplog):
    caplog.set_level("WARNING")
    stop = threading.Event()
    errors = []

    def mutate():
        i = 0
        while not stop.is_set():
            logs = task_mgr.sessions[SID]["logs"]
            logs.append(f"line {i}")
            if len(logs) > 200:
                del logs[:100]
            task_mgr.sessions[SID][f"k{i % 50}"] = {"n": i}
            i += 1

    def save():
        try:
            for _ in range(10):
                task_mgr._save_session(SID)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    mutator = threading.Thread(target=mutate)
    mutator.start()
    savers = [threading.Thread(target=save) for _ in range(4)]
    for t in savers:
        t.start()
    for t in savers:
        t.join()
    stop.set()
    mutator.join()

    assert not errors
    assert not [r for r in caplog.records if "持久化会话" in r.getMessage()]
    data = _read(store)
    assert data["session_id"] == SID and isinstance(data["logs"], list)
    assert not list(store.glob(f"{SID}*.tmp"))


def test_rename_persists_title(store):
    resp = asyncio.run(rename_session(SID, {"title": "重命名后"}))
    assert json.loads(resp.body)["success"] is True
    assert _read(store)["title"] == "重命名后"
