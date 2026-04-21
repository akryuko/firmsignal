from firmsignal.tools.cache import _cache_key

def test_cache_key_is_deterministic():
    assert _cache_key("Nvidia 2026") == _cache_key("Nvidia 2026")

def test_cache_key_is_case_insensitive():
    assert _cache_key("NVIDIA") == _cache_key("nvidia")

def test_cache_key_strips_whitespace():
    assert _cache_key("  Nvidia  ") == _cache_key("Nvidia")

def test_different_queries_different_keys():
    assert _cache_key("Nvidia news") != _cache_key("Boeing news")