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


def test_ask_endpoint_returns_agent_plan_and_grounded_analysis() -> None:
    response = client.post(
        "/api/v1/ask",
        json={"question": "支付转化率最近表现如何？", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    tool_evidence_keys = {
        item["evidence_key"]
        for item in body["tool_results"]
        if item["status"] == "ok"
    }

    assert body["provider"] in {"deterministic", "openai"}
    assert body["analysis"]["summary"]
    assert body["data_version"]
    assert body["request_id"]
    assert body["plan"]["planner_version"]
    assert any(call["tool"] == "compare_periods" for call in body["plan"]["calls"])
    assert any(
        item["metric"] == "pay_conversion_rate"
        for item in body["evidence"]
    )
    assert all(
        set(item["evidence_keys"]).issubset(tool_evidence_keys)
        for item in body["analysis"]["observations"]
    )


def test_agent_surfaces_missing_serving_dimension() -> None:
    response = client.post(
        "/api/v1/ask",
        json={"question": "按渠道分析 GMV", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert "channel" in body["plan"]["coverage_gaps"]
    assert any("channel" in warning for warning in body["warnings"])


def test_prometheus_endpoint_is_exposed() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "retailpulse_http_requests_total" in response.text
    assert "retailpulse_agent_tool_calls_total" in response.text
