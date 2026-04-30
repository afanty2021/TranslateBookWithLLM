import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.llm.utils.language import language_to_code, LANG_MAP


class TestLanguageUtils:
    def test_common_languages(self):
        assert language_to_code("English") == "en"
        assert language_to_code("chinese") == "zh"
        assert language_to_code("French") == "fr"
        assert language_to_code("Japanese") == "ja"

    def test_already_code(self):
        assert language_to_code("en") == "en"
        assert language_to_code("zh") == "zh"

    def test_empty(self):
        assert language_to_code("") == ""
        assert language_to_code("klingon") == "klingon"

    def test_whitespace_handling(self):
        assert language_to_code("  English  ") == "en"
        assert language_to_code(" Chinese") == "zh"

    def test_lang_map_superset(self):
        """Verify LANG_MAP has all languages from both original files."""
        # Languages that were in both mlx.py and mlx_direct.py
        required = [
            "english", "chinese", "french", "german", "spanish",
            "japanese", "korean", "russian", "italian", "portuguese",
            "arabic", "hindi",
        ]
        for lang in required:
            assert lang in LANG_MAP, f"Missing language: {lang}"

    def test_mlx_providers_use_shared(self):
        """Verify mlx providers import the shared utility, not local dicts."""
        for filepath in [
            'src/core/llm/providers/mlx.py',
            'src/core/llm/providers/mlx_direct.py',
        ]:
            with open(filepath, 'r') as f:
                content = f.read()
            assert 'language_to_code' in content, f"{filepath} does not reference language_to_code"
            # No local lang_map dict definitions
            lines_with_lang_map = [
                l for l in content.split('\n')
                if 'lang_map' in l.lower() and '=' in l and '{' in l
            ]
            assert len(lines_with_lang_map) == 0, (
                f"{filepath} still has local lang_map dict on lines: {lines_with_lang_map}"
            )
