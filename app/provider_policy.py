import os

from app.provider_circuit import CircuitBreaker


def breaker_from_env() -> CircuitBreaker:
    threshold = int(os.getenv("RETAILPULSE_PROVIDER_FAILURE_THRESHOLD", "3"))
    cooldown = float(os.getenv("RETAILPULSE_PROVIDER_COOLDOWN_SECONDS", "30"))
    if threshold < 1 or cooldown < 0:
        raise ValueError("provider circuit settings are invalid")
    return CircuitBreaker(threshold, cooldown)
