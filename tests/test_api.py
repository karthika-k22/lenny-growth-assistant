from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200


def test_models_endpoint():
    response = client.get("/api/models")

    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))


def test_conversations_endpoint():
    response = client.get("/api/conversations")

    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))


def test_artifacts_endpoint():
    response = client.get("/api/artifacts")

    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))
