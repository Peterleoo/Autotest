# -*- coding: utf-8 -*-
"""P1-7 动作后等待：界面稳定提前放行，检测失败退化为原固定时长"""
import time

import pytest

import ai_engine.test_agent as agent_module
from ai_engine.test_agent import AITestAgent


@pytest.fixture
def agent():
    inst = object.__new__(AITestAgent)
    inst.driver = object()
    return inst


def _timed(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def test_returns_early_when_screen_settles(agent, monkeypatch):
    calls = []
    monkeypatch.setattr(agent_module.ScreenParser, "wait_for_visual_settling",
                        lambda driver, max_wait: calls.append(max_wait))
    elapsed = _timed(lambda: agent._wait_ui_settled(1.5))
    assert calls == [pytest.approx(1.5 - AITestAgent.UI_SETTLE_MIN_DWELL)]
    assert AITestAgent.UI_SETTLE_MIN_DWELL <= elapsed < 1.0


def test_falls_back_to_fixed_wait_when_detection_fails(agent, monkeypatch):
    def boom(driver, max_wait):
        raise RuntimeError("screencap failed")

    monkeypatch.setattr(agent_module.ScreenParser, "wait_for_visual_settling", boom)
    elapsed = _timed(lambda: agent._wait_ui_settled(0.6))
    assert 0.55 <= elapsed < 0.9


def test_short_wait_only_dwells_without_detection(agent, monkeypatch):
    called = []
    monkeypatch.setattr(agent_module.ScreenParser, "wait_for_visual_settling",
                        lambda driver, max_wait: called.append(max_wait))
    elapsed = _timed(lambda: agent._wait_ui_settled(0.2))
    assert called == []
    assert 0.18 <= elapsed < 0.4
