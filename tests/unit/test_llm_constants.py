import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.llm.constants import CONTEXT_OVERFLOW_KEYWORDS, default_retry_wait


class TestLLMConstants:
    def test_keywords_is_list(self):
        assert isinstance(CONTEXT_OVERFLOW_KEYWORDS, list)
        assert len(CONTEXT_OVERFLOW_KEYWORDS) >= 10

    def test_keywords_all_lowercase(self):
        for kw in CONTEXT_OVERFLOW_KEYWORDS:
            assert kw == kw.lower(), f"Keyword not lowercase: {kw}"

    def test_default_retry_wait(self):
        assert default_retry_wait(0) == 4
        assert default_retry_wait(1) == 8
        assert default_retry_wait(3) == 32
        assert default_retry_wait(10) == 60  # capped

    def test_providers_use_base_class_methods(self):
        """验证各 provider 使用基类的错误处理方法，而非直接导入常量"""
        base = os.path.join(os.path.dirname(__file__), '..', '..')
        provider_files = [
            'src/core/llm/providers/openai.py',
            'src/core/llm/providers/deepseek.py',
            'src/core/llm/providers/mistral.py',
            'src/core/llm/providers/openrouter.py',
            'src/core/llm/providers/poe.py',
        ]
        for filepath in provider_files:
            full_path = os.path.join(base, filepath)
            with open(full_path, 'r') as f:
                content = f.read()
            # 应使用基类方法
            assert 'self._is_context_overflow(' in content, f"{filepath} should use self._is_context_overflow()"
            assert 'self._is_rate_limited(' in content, f"{filepath} should use self._is_rate_limited()"
            assert 'self._get_retry_wait(' in content, f"{filepath} should use self._get_retry_wait()"
            # 不应直接导入常量（已迁移到基类）
            assert 'from ..constants import' not in content, f"{filepath} should not import from constants directly"
            # 不应再有局部定义
            assert 'context_overflow_keywords = [' not in content, f"{filepath} still has local keywords"
