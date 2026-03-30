from app.config import Settings

def test_llm_config_defaults():
    s = Settings()
    assert s.llm_provider == "openai_compatible"
    assert s.llm_tier1_model == "qwen-turbo"
    assert s.llm_tier2_model == "qwen-plus"
    assert s.llm_tier3_model == "qwen-max"
    assert s.llm_timeout_seconds == 30
    assert s.llm_max_retries == 2
    assert s.llm_batch_size == 20
    assert s.llm_circuit_breaker_threshold == 5
    assert s.llm_base_url == ""
    assert s.llm_api_key == ""
    assert s.llm_process_interval_minutes == 10
