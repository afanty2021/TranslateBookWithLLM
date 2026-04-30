"""LLM Provider 共享常量"""

# 上下文溢出错误关键词 — 所有 provider 共用
CONTEXT_OVERFLOW_KEYWORDS = [
    "context_length",
    "maximum context",
    "token limit",
    "context window",
    "max_tokens",
    "context_length_exceeded",
    "too many tokens",
    "input is too long",
    "maximum context length",
    "exceeds the maximum",
    "reduce the length",
    "exceeds",
]


def default_retry_wait(attempt: int, max_wait: int = 60) -> int:
    """指数退避等待时间：2^(attempt+2)，上限 max_wait"""
    return min(2 ** (attempt + 2), max_wait)
