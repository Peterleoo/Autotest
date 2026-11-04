# -*- coding: utf-8 -*-
"""大模型真实 Token 用量统计

子进程 (run_ai_test.py) 每次调用模型后输出一行 `[TOKEN_USAGE] ...`，
父进程 (task_device_pipeline) 读取 stdout 时解析并累加到会话 token_stats，
与既有的 `[WAIT_HITL_DECISION]` 行协议一致，无需父子进程共享内存或抢写会话文件。
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

USAGE_TAG = "[TOKEN_USAGE]"
_USAGE_RE = re.compile(
    r"\[TOKEN_USAGE\] prompt=(?P<prompt>\d+) completion=(?P<completion>\d+) total=(?P<total>\d+)"
    r"(?: model=(?P<model>\S+))?"
)


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""

    @property
    def is_empty(self) -> bool:
        return self.total_tokens <= 0

    @staticmethod
    def from_gemini(meta: Optional[Dict[str, Any]], model: str = "") -> "TokenUsage":
        """Gemini / Antigravity usageMetadata：思考 token 按输出计费，计入 completion"""
        meta = meta or {}
        prompt = int(meta.get("promptTokenCount") or 0)
        completion = int(meta.get("candidatesTokenCount") or 0) + int(meta.get("thoughtsTokenCount") or 0)
        total = int(meta.get("totalTokenCount") or 0) or prompt + completion
        return TokenUsage(prompt, completion, total, model)

    @staticmethod
    def from_openai(usage: Any, model: str = "") -> "TokenUsage":
        """OpenAI / DeepSeek / Hermes 兼容协议的 response.usage"""
        if usage is None:
            return TokenUsage(model=model)
        prompt = int(_field(usage, "prompt_tokens"))
        completion = int(_field(usage, "completion_tokens"))
        total = int(_field(usage, "total_tokens")) or prompt + completion
        return TokenUsage(prompt, completion, total, model)

    @staticmethod
    def from_anthropic(usage: Any, model: str = "") -> "TokenUsage":
        """Anthropic Messages API 的 response.usage（无 total 字段，需自行求和）"""
        if usage is None:
            return TokenUsage(model=model)
        prompt = int(_field(usage, "input_tokens")) + int(_field(usage, "cache_read_input_tokens")) \
            + int(_field(usage, "cache_creation_input_tokens"))
        completion = int(_field(usage, "output_tokens"))
        return TokenUsage(prompt, completion, prompt + completion, model)


def _field(obj: Any, name: str) -> int:
    value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, 0)
    return value or 0


def format_usage_line(usage: TokenUsage) -> str:
    line = f"{USAGE_TAG} prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}"
    return f"{line} model={usage.model}" if usage.model else line


def parse_usage_line(line: str) -> Optional[TokenUsage]:
    """从日志行中解析用量；非用量行返回 None"""
    if USAGE_TAG not in line:
        return None
    m = _USAGE_RE.search(line)
    if not m:
        return None
    return TokenUsage(int(m["prompt"]), int(m["completion"]), int(m["total"]), m["model"] or "")


def accumulate(token_stats: Optional[Dict[str, Any]], usage: TokenUsage) -> Dict[str, Any]:
    """返回累加后的新 token_stats（不修改入参），保留 context_window 等既有字段"""
    stats = dict(token_stats or {})
    stats["total_tokens"] = int(stats.get("total_tokens") or 0) + usage.total_tokens
    stats["prompt_tokens"] = int(stats.get("prompt_tokens") or 0) + usage.prompt_tokens
    stats["completion_tokens"] = int(stats.get("completion_tokens") or 0) + usage.completion_tokens
    stats["llm_calls"] = int(stats.get("llm_calls") or 0) + 1
    if usage.model:
        by_model = dict(stats.get("by_model") or {})
        by_model[usage.model] = int(by_model.get(usage.model) or 0) + usage.total_tokens
        stats["by_model"] = by_model
    stats["source"] = "provider_reported"
    return stats
