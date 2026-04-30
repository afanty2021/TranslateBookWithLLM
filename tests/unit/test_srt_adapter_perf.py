"""
Tests for SrtAdapter performance optimizations.
Verifies O(1) caching and index mapping instead of O(n^2) linear scans.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestSrtAdapterPerf:
    """Tests that the SrtAdapter uses caching and avoids O(n) index() calls."""

    def test_get_translation_units_caches(self):
        """get_translation_units should cache results via _units_cache."""
        from src.core.adapters.srt_adapter import SrtAdapter
        import inspect

        source = inspect.getsource(SrtAdapter.get_translation_units)
        # Should have cache check at the top
        assert '_units_cache' in source, (
            "get_translation_units should reference _units_cache for caching"
        )
        # Should return early when cache is populated
        assert 'if self._units_cache is not None' in source, (
            "get_translation_units should check if _units_cache is not None and return early"
        )

    def test_no_linear_index_search(self):
        """Should not use self.subtitles.index() for linear search in hot paths."""
        from src.core.adapters.srt_adapter import SrtAdapter
        import inspect

        source = inspect.getsource(SrtAdapter.get_translation_units)
        lines = source.split('\n')
        for line in lines:
            stripped = line.strip()
            # Allow fallback in conditional branches (inside 'if ... is None')
            # But no unconditional self.subtitles.index() calls
            if 'self.subtitles.index(' in stripped:
                # Must be a fallback inside a conditional (indented inside an if block)
                # Check that this line is NOT the primary/only way to find index
                assert 'if global_idx is None' in source or 'if idx is None' in source, (
                    f"Found unconditional O(n) index() call: {stripped}. "
                    "Should use _subtitle_index dict as primary lookup."
                )

    def test_subtitle_index_dict_built(self):
        """prepare_for_translation should build _subtitle_index dict."""
        from src.core.adapters.srt_adapter import SrtAdapter
        import inspect

        source = inspect.getsource(SrtAdapter.prepare_for_translation)
        assert '_subtitle_index' in source, (
            "prepare_for_translation should build _subtitle_index for O(1) lookups"
        )
        assert 'id(s)' in source or 'id(subtitle' in source, (
            "_subtitle_index should use id() as key for dict-based lookup"
        )

    def test_cache_invalidated_on_save(self):
        """save_unit_translation should invalidate the units cache."""
        from src.core.adapters.srt_adapter import SrtAdapter
        import inspect

        source = inspect.getsource(SrtAdapter.save_unit_translation)
        assert '_units_cache = None' in source or '_units_cache=None' in source, (
            "save_unit_translation should set self._units_cache = None to invalidate"
        )

    def test_cache_attribute_initialized(self):
        """__init__ should initialize _units_cache."""
        from src.core.adapters.srt_adapter import SrtAdapter
        import inspect

        source = inspect.getsource(SrtAdapter.__init__)
        assert '_units_cache' in source, (
            "__init__ should initialize self._units_cache"
        )
        assert '_subtitle_index' in source, (
            "__init__ should initialize self._subtitle_index"
        )

    def test_uses_dict_lookup_in_get_units(self):
        """get_translation_units should use _subtitle_index.get() for O(1) lookup."""
        from src.core.adapters.srt_adapter import SrtAdapter
        import inspect

        source = inspect.getsource(SrtAdapter.get_translation_units)
        assert '_subtitle_index.get(id(' in source, (
            "get_translation_units should use self._subtitle_index.get(id(...)) "
            "for O(1) lookups instead of self.subtitles.index()"
        )
