# -*- coding: utf-8 -*-
"""真实 token 用量：服务商回报 -> [TOKEN_USAGE] 行 -> 父进程累加到会话 token_stats -> 前端展示"""
import logging
from types import SimpleNamespace

from core.token_usage import TokenUsage, accumulate, format_usage_line, parse_usage_line


def test_gemini_usage_counts_thinking_tokens_as_output():
    u = TokenUsage.from_gemini({"promptTokenCount": 3000, "candidatesTokenCount": 200,
                                "thoughtsTokenCount": 50, "totalTokenCount": 3250}, "gemini-2.5-flash")
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (3000, 250, 3250)


def test_gemini_usage_missing_metadata_is_empty():
    assert TokenUsage.from_gemini(None).is_empty


def test_openai_and_anthropic_usage():
    o = TokenUsage.from_openai(SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15), "deepseek")
    a = TokenUsage.from_anthropic(SimpleNamespace(input_tokens=100, output_tokens=20,
                                                  cache_read_input_tokens=30, cache_creation_input_tokens=0), "claude")
    assert o.total_tokens == 15
    assert (a.prompt_tokens, a.completion_tokens, a.total_tokens) == (130, 20, 150)


def test_usage_line_roundtrip_inside_log_prefix():
    u = TokenUsage(1200, 300, 1500, "gemini-2.5-flash")
    line = f"2026-11-04 17:20:27,222 [INFO] {format_usage_line(u)}"
    assert parse_usage_line(line) == u
    assert parse_usage_line("2026-11-04 [INFO] 普通日志") is None


def test_accumulate_is_immutable_and_sums_per_model():
    base = {"total_tokens": 0, "context_window": 1048576, "pressure_level": "normal"}
    s1 = accumulate(base, TokenUsage(1000, 100, 1100, "gemini-2.5-flash"))
    s2 = accumulate(s1, TokenUsage(500, 50, 550, "hermes-model"))
    assert base["total_tokens"] == 0  # 入参不被修改
    assert s2["total_tokens"] == 1650 and s2["prompt_tokens"] == 1500 and s2["completion_tokens"] == 150
    assert s2["llm_calls"] == 2
    assert s2["by_model"] == {"gemini-2.5-flash": 1100, "hermes-model": 550}
    assert s2["context_window"] == 1048576


def test_antigravity_response_records_usage(monkeypatch):
    from core.antigravity_direct import AntigravityDirectClient
    client = AntigravityDirectClient.__new__(AntigravityDirectClient)  # 跳过联网初始化
    data = {"response": {
        "candidates": [{"content": {"parts": [{"text": '{"action": "tap"}'}]}}],
        "usageMetadata": {"promptTokenCount": 4100, "candidatesTokenCount": 180, "totalTokenCount": 4280},
    }}
    result = client._consume_response(data, "gemini-2.5-flash")
    assert result["action"] == "tap"
    assert client.last_usage == TokenUsage(4100, 180, 4280, "gemini-2.5-flash")


def test_llm_client_emits_usage_line(caplog):
    from core.llm_client import LLMClient
    client = LLMClient.__new__(LLMClient)
    with caplog.at_level(logging.INFO):
        client._report_usage(TokenUsage(10, 2, 12, "m"))
        client._report_usage(TokenUsage())  # 空用量不输出
    lines = [r.getMessage() for r in caplog.records if "[TOKEN_USAGE]" in r.getMessage()]
    assert lines == ["[TOKEN_USAGE] prompt=10 completion=2 total=12 model=m"]


def test_pipeline_accumulates_usage_lines():
    import inspect
    from core import task_device_pipeline
    src = inspect.getsource(task_device_pipeline)
    assert "parse_usage_line(line)" in src and 'session["token_stats"] = accumulate(' in src


def test_frontend_shows_token_pill_only_with_real_data():
    from tests.frontend_source import read_frontend_source
    js = read_frontend_source()
    assert "function buildTokenUsagePill(sessionData)" in js
    assert "if (total <= 0) return \"\";" in js
    assert js.count("${buildTokenUsagePill(sessionData)}") == 2
