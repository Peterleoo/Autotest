# -*- coding: utf-8 -*-
"""P1-9 Antigravity OAuth 配置路径不得写死本机盘符，外部桥接文件改由环境变量指定"""
import importlib

import core.antigravity_oauth as oauth_module


def _reload(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ANTIGRAVITY_OAUTH_BRIDGE_FILE", raising=False)
    else:
        monkeypatch.setenv("ANTIGRAVITY_OAUTH_BRIDGE_FILE", value)
    return importlib.reload(oauth_module)


def test_only_local_config_without_env(monkeypatch):
    try:
        mod = _reload(monkeypatch, None)
        assert len(mod.CONFIG_PATHS) == 1
        assert mod.CONFIG_PATHS[0].name == "antigravity_oauth.json"
        assert not any("PM-product" in str(p) for p in mod.CONFIG_PATHS)
    finally:
        monkeypatch.undo()
        importlib.reload(oauth_module)


def test_bridge_file_from_env_is_appended_as_fallback(monkeypatch, tmp_path):
    bridge = tmp_path / "bridge.json"
    try:
        mod = _reload(monkeypatch, str(bridge))
        assert mod.CONFIG_PATHS[0].name == "antigravity_oauth.json"
        assert mod.CONFIG_PATHS[1] == bridge
    finally:
        monkeypatch.undo()
        importlib.reload(oauth_module)
