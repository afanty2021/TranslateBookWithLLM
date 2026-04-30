import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.epub.epub_translate_helpers import EPUBTranslateHelper


class TestEPUBTranslateHelper:
    def test_extract_translatable_nodes_basic(self):
        helper = EPUBTranslateHelper(provider=None)
        html = "<p>Hello world</p><p>Test paragraph</p>"
        nodes = helper.extract_translatable_nodes(html)
        assert len(nodes) >= 1
        texts = [n[0] for n in nodes]
        assert "Hello world" in texts

    def test_extract_translatable_nodes_filters_short(self):
        """Text shorter than 10 chars should be excluded"""
        helper = EPUBTranslateHelper(provider=None)
        html = "<p>Hi</p><p>Short</p>"
        nodes = helper.extract_translatable_nodes(html)
        assert len(nodes) == 0

    def test_extract_translatable_nodes_requires_letters(self):
        """Nodes without 3+ consecutive letters should be excluded"""
        helper = EPUBTranslateHelper(provider=None)
        html = "<p>123456789012345</p>"
        nodes = helper.extract_translatable_nodes(html)
        assert len(nodes) == 0

    def test_extract_translatable_nodes_returns_positions(self):
        """Should return (text, start, end) tuples"""
        helper = EPUBTranslateHelper(provider=None)
        html = "<p>Hello world testing</p>"
        nodes = helper.extract_translatable_nodes(html)
        assert len(nodes) >= 1
        text, start, end = nodes[0]
        assert text == "Hello world testing"
        assert isinstance(start, int)
        assert isinstance(end, int)
        assert html[start:end] == text

    def test_replace_in_html(self):
        html = "<p>Hello world</p>"
        replacements = [("Hello world", "你好世界", 3, 14)]
        result = EPUBTranslateHelper.replace_in_html(html, replacements)
        assert "你好世界" in result
        assert "Hello world" not in result

    def test_replace_in_html_multiple(self):
        html = "<p>AAA</p><p>BBB</p>"
        replacements = [
            ("AAA", "aaa", 3, 6),
            ("BBB", "bbb", 13, 16),
        ]
        result = EPUBTranslateHelper.replace_in_html(html, replacements)
        assert "aaa" in result
        assert "bbb" in result

    def test_replace_in_html_empty_replacements(self):
        html = "<p>Hello</p>"
        result = EPUBTranslateHelper.replace_in_html(html, [])
        assert result == html

    def test_replace_in_html_static_method(self):
        """replace_in_html should work without an instance"""
        result = EPUBTranslateHelper.replace_in_html(
            "<p>test</p>", [("test", "测试", 3, 7)]
        )
        assert "测试" in result

    def test_log_callback(self):
        messages = []
        helper = EPUBTranslateHelper(
            provider=None,
            log_callback=lambda l, m: messages.append((l, m)),
        )
        helper.log("info", "test message")
        assert len(messages) == 1
        assert messages[0] == ("info", "test message")

    def test_log_no_callback(self):
        """Log without callback should not crash"""
        helper = EPUBTranslateHelper(provider=None)
        helper.log("info", "test")  # Should print to stdout

    def test_scripts_import_from_shared(self):
        """验证 4 个脚本从共享模块导入"""
        base_dir = os.path.join(os.path.dirname(__file__), '..', '..')
        for filepath in [
            'translate_epub_robust.py',
            'translate_epub_by_chapter.py',
            'translate_epub_isolated.py',
            'translate_epub_parallel_robust.py',
        ]:
            full_path = os.path.join(base_dir, filepath)
            if not os.path.exists(full_path):
                continue
            with open(full_path, 'r') as f:
                content = f.read()
            assert 'EPUBTranslateHelper' in content or 'epub_translate_helpers' in content, \
                f"{filepath} should import from epub_translate_helpers"
