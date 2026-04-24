from sebastian.context.token_meter import ContextTokenMeter
from sebastian.context.usage import TokenUsage


def test_meter_uses_reported_usage_threshold() -> None:
    meter = ContextTokenMeter(context_window=100_000)

    decision = meter.should_compact(usage=TokenUsage(input_tokens=70_000), estimate=None)

    assert decision.should_compact is True
    assert decision.reason == "usage_threshold"


def test_meter_uses_lower_estimate_threshold() -> None:
    meter = ContextTokenMeter(context_window=100_000)

    decision = meter.should_compact(usage=None, estimate=65_000)

    assert decision.should_compact is True
    assert decision.reason == "estimate_threshold"


def test_meter_returns_no_data_reason_when_both_inputs_missing() -> None:
    meter = ContextTokenMeter(context_window=100_000)

    decision = meter.should_compact(usage=None, estimate=None)

    assert decision.should_compact is False
    assert decision.reason == "no_data"
    assert decision.token_count is None
