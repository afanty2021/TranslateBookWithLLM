import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.llm.utils.logging import LLMLogger


class TestLLMLogger:
    def test_warning_with_callback(self):
        messages = []
        logger = LLMLogger("test", log_callback=lambda l, m: messages.append((l, m)))
        logger.warning("test warning")
        assert len(messages) == 1
        assert messages[0][0] == "llm_warning"
        assert "test warning" in messages[0][1]

    def test_error_with_callback(self):
        messages = []
        logger = LLMLogger("test", log_callback=lambda l, m: messages.append((l, m)))
        logger.error("test error")
        assert len(messages) == 1
        assert messages[0][0] == "llm_error"

    def test_info_with_callback(self):
        messages = []
        logger = LLMLogger("test", log_callback=lambda l, m: messages.append((l, m)))
        logger.info("test info")
        assert len(messages) == 1
        assert messages[0][0] == "llm_info"

    def test_rate_limit(self):
        messages = []
        logger = LLMLogger("test", log_callback=lambda l, m: messages.append((l, m)))
        logger.rate_limit(0, 3, 10)
        assert len(messages) == 1
        assert "attempt 1/3" in messages[0][1]

    def test_no_color_in_non_tty(self):
        logger = LLMLogger("test", log_callback=lambda l, m: None)
        logger._is_tty = False
        result = logger._colorize("test", "91")
        assert "\033[" not in result

    def test_no_ansi_in_providers(self):
        """验证所有 provider 文件无 ANSI 硬编码"""
        import glob
        for filepath in glob.glob('src/core/llm/providers/*.py'):
            with open(filepath, 'r') as f:
                content = f.read()
            assert "RED = '\\033[" not in content, f"{filepath} still has hardcoded RED"
            assert "YELLOW = '\\033[" not in content, f"{filepath} still has hardcoded YELLOW"
