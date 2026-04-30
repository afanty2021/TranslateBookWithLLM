"""质量改进修复的单元测试"""
import os
import sys
import pytest

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestCORSSecurity:
    def test_cors_not_wildcard(self):
        """CORS 不应允许任意来源"""
        with open('translation_api.py', 'r') as f:
            content = f.read()
        assert 'CORS(app)' not in content or 'origins=' in content
        assert 'cors_allowed_origins="*"' not in content

    def test_socketio_origins_restricted(self):
        """SocketIO origins 应限制为 localhost"""
        with open('translation_api.py', 'r') as f:
            content = f.read()
        assert 'localhost' in content or '127.0.0.1' in content


class TestNoApiKeyInGetParams:
    def test_get_models_does_not_read_api_key_from_query(self):
        """GET /api/models 不应从 URL 查询参数读取 api_key（安全问题）"""
        with open('src/api/blueprints/config_routes.py', 'r') as f:
            content = f.read()
        assert "request.args.get('api_key')" not in content


class TestApiKeySanitization:
    def test_to_dict_masks_api_keys(self):
        from src.config import TranslationConfig
        config = TranslationConfig(
            openai_api_key="sk-test-secret-key-12345",
            gemini_api_key="AIza-test-secret-67890",
        )
        d = config.to_dict()
        assert "sk-test-secret-key-12345" not in str(d)
        assert "AIza-test-secret-67890" not in str(d)
        assert d.get("openai_api_key", "").endswith("2345")
        assert d.get("gemini_api_key", "").endswith("7890")

    def test_to_dict_masks_all_key_fields(self):
        from src.config import TranslationConfig
        config = TranslationConfig(
            openrouter_api_key="sk-or-long-key-9876",
            mistral_api_key="mist-long-key-5432",
            deepseek_api_key="ds-long-secret-key-1111",
            poe_api_key="poe-long-secret-key-2222",
            nim_api_key="nv-long-secret-key-3333",
            mlx_api_key="mlx-long-secret-key-4444",
        )
        d = config.to_dict()
        for key_field, original in [
            ("openrouter_api_key", "sk-or-long-key-9876"),
            ("mistral_api_key", "mist-long-key-5432"),
            ("deepseek_api_key", "ds-long-secret-key-1111"),
            ("poe_api_key", "poe-long-secret-key-2222"),
            ("nim_api_key", "nv-long-secret-key-3333"),
            ("mlx_api_key", "mlx-long-secret-key-4444"),
        ]:
            assert original not in str(d), f"{key_field} not masked"
            assert d[key_field].startswith("***"), f"{key_field} not masked"

    def test_to_dict_short_key_masked(self):
        """Short keys (< 8 chars) should be fully masked"""
        from src.config import TranslationConfig
        config = TranslationConfig(
            openai_api_key="short",
        )
        d = config.to_dict()
        assert d["openai_api_key"] == "***"

    def test_to_dict_empty_key(self):
        """Empty keys should remain empty"""
        from src.config import TranslationConfig
        config = TranslationConfig(
            openai_api_key="",
        )
        d = config.to_dict()
        assert d["openai_api_key"] == ""

    def test_to_dict_non_key_fields_unchanged(self):
        """Non-key fields should pass through unchanged"""
        from src.config import TranslationConfig
        config = TranslationConfig(
            source_language="English",
            target_language="Chinese",
            model="qwen3:14b",
        )
        d = config.to_dict()
        assert d["source_language"] == "English"
        assert d["target_language"] == "Chinese"
        assert d["model"] == "qwen3:14b"


class TestNoHardcodedSecrets:
    _FILES = ['check_poe_models.py', 'test_cleanup.py', 'test_epub_translation.py', 'test_simple_api.py']
    _PATTERNS = ['rEhgy', 'siRfoz', 'sk-or-']

    def test_no_hardcoded_api_keys(self):
        for filepath in self._FILES:
            if not os.path.exists(filepath):
                continue
            with open(filepath, 'r') as f:
                content = f.read()
            for pattern in self._PATTERNS:
                assert pattern not in content, f"Found '{pattern}' in {filepath}"


class TestPathTraversal:
    def test_security_py_uses_is_relative_to(self):
        with open('src/utils/security.py', 'r') as f:
            content = f.read()
        # No startswith path validation remains (replaced by is_relative_to)
        assert 'is_relative_to' in content

    def test_verify_endpoint_restricts_to_upload_dir(self):
        with open('src/api/blueprints/security_routes.py', 'r') as f:
            content = f.read()
        verify_section = content.split('def verify_uploaded_files')[1].split('\ndef ')[0]
        assert 'upload_dir_resolved' in verify_section
        assert 'is_relative_to' in verify_section

    def test_security_routes_uses_is_relative_to(self):
        with open('src/api/blueprints/security_routes.py', 'r') as f:
            content = f.read()
        assert 'is_relative_to' in content
        # Should not have startswith path checks anymore
        assert 'str(resolved).startswith' not in content

    def test_file_service_uses_is_relative_to(self):
        with open('src/api/services/file_service.py', 'r') as f:
            content = f.read()
        assert 'is_relative_to' in content
        assert 'str(file_path_resolved).startswith' not in content
