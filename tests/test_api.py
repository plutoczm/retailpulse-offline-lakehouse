from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_readiness() -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_ask_endpoint_returns_evidence() -> None:
    response = client.post(
        "/api/v1/ask",
        json={"question": "支付转化率最近表现如何？", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] in {"deterministic", "openai"}
    assert any(item["metric"] == "pay_conversion_rate" for item in body["evidence"])
    assert body["request_id"]
