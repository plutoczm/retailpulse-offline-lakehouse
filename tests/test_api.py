from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_readiness() -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    ready = client.get("/readyz")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "ready"
    assert body["data_version"]
    assert body["source_kind"] in {"lakehouse", "demo"}


def test_ask_endpoint_returns_structured_grounded_analysis() -> None:
    response = client.post(
        "/api/v1/ask",
        json={"question": "支付转化率最近表现如何？", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    evidence_keys = {item["metric"] for item in body["evidence"]}

    assert body["provider"] in {"deterministic", "openai"}
    assert body["analysis"]["summary"]
    assert body["data_version"]
    assert body["request_id"]
    assert any(item["metric"] == "pay_conversion_rate" for item in body["evidence"])
    assert all(
        set(item["evidence_keys"]).issubset(evidence_keys)
        for item in body["analysis"]["observations"]
    )


def test_prometheus_endpoint_is_exposed() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "retailpulse_http_requests_total" in response.text
