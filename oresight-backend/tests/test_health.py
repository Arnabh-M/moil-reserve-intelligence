from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_status_and_expected_shape():
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "oresight-api"
    assert body["db"] in {"connected", "unavailable"}
    assert body["neo4j"] in {"connected", "unavailable"}
