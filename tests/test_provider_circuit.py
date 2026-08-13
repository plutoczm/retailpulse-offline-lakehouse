from app.provider_circuit import CircuitBreaker


def test_breaker_opens_and_allows_one_half_open_probe() -> None:
    breaker = CircuitBreaker(threshold=2, cooldown_seconds=10)
    assert breaker.allow(now=0)
    breaker.failure(now=0)
    assert breaker.allow(now=1)
    breaker.failure(now=1)
    assert not breaker.allow(now=2)
    assert breaker.allow(now=11)
    assert not breaker.allow(now=11)
    breaker.failure(now=11)
    assert not breaker.allow(now=12)
    assert breaker.allow(now=21)
    breaker.success()
    assert breaker.allow(now=21)
