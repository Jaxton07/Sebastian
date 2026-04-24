from sebastian.context.estimator import TokenEstimator


def test_estimator_counts_chinese_conservatively() -> None:
    estimator = TokenEstimator()

    assert estimator.estimate_text("你好世界，这是一个测试") >= 6


def test_estimator_counts_message_structure_overhead() -> None:
    estimator = TokenEstimator()
    tokens = estimator.estimate_messages(
        [{"role": "user", "content": "hello"}],
        system_prompt="system",
    )

    assert tokens > estimator.estimate_text("hellosystem")
