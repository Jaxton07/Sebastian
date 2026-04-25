from sebastian.context.usage import TokenUsage


def test_token_usage_effective_input_includes_cache_tokens() -> None:
    usage = TokenUsage(
        input_tokens=10,
        cache_creation_input_tokens=20,
        cache_read_input_tokens=30,
        output_tokens=5,
    )

    assert usage.effective_input_tokens == 60
    assert usage.effective_total_tokens == 65


def test_token_usage_missing_values_are_zero_for_effective_counts() -> None:
    usage = TokenUsage(output_tokens=7)

    assert usage.effective_input_tokens is None
    assert usage.effective_total_tokens is None
