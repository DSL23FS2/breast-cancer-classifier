"""Integration-тесты FastAPI через httpx."""
import pytest
from fastapi.testclient import TestClient
from src.api import app


# TestClient используется как контекстный менеджер через фикстуру,
# чтобы корректно запустить lifespan (startup/shutdown).
# В Starlette ≥ 0.21 lifespan срабатывает только при входе в __enter__.
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


MALIGNANT_FEATURES = [
    17.99, 10.38, 122.8, 1001.0, 0.1184, 0.2776, 0.3001, 0.1471,
    0.2419, 0.07871, 1.095, 0.9053, 8.589, 153.4, 0.006399,
    0.04904, 0.05373, 0.01587, 0.03003, 0.006193, 25.38, 17.33,
    184.6, 2019.0, 0.1622, 0.6656, 0.7119, 0.2654, 0.4601, 0.1189
]

BENIGN_FEATURES = [
    13.54, 14.36, 87.46, 566.3, 0.09779, 0.08129, 0.06664, 0.04781,
    0.1885, 0.05766, 0.2699, 0.7886, 2.058, 23.56, 0.008462,
    0.0146, 0.02387, 0.01315, 0.0198, 0.0023, 15.11, 19.26,
    99.7, 711.2, 0.144, 0.1773, 0.239, 0.1288, 0.2977, 0.07259
]


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_status_field(self, client):
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_health_model_loaded(self, client):
        resp = client.get("/health")
        assert resp.json()["model_loaded"] is True


class TestPredict:
    def test_predict_200(self, client):
        resp = client.post("/predict", json={"features": MALIGNANT_FEATURES})
        assert resp.status_code == 200

    def test_predict_response_schema(self, client):
        resp = client.post("/predict", json={"features": MALIGNANT_FEATURES})
        data = resp.json()
        assert "prediction" in data
        assert "probability" in data
        assert "label" in data

    def test_predict_malignant(self, client):
        resp = client.post("/predict", json={"features": MALIGNANT_FEATURES})
        data = resp.json()
        assert data["prediction"] == 0
        assert data["label"] == "malignant"

    def test_predict_benign(self, client):
        resp = client.post("/predict", json={"features": BENIGN_FEATURES})
        data = resp.json()
        assert data["prediction"] == 1
        assert data["label"] == "benign"

    def test_predict_probability_range(self, client):
        resp = client.post("/predict", json={"features": MALIGNANT_FEATURES})
        prob = resp.json()["probability"]
        assert 0.0 <= prob <= 1.0


class TestPredictValidation:
    def test_wrong_feature_count_422(self, client):
        resp = client.post("/predict", json={"features": [1.0] * 10})
        assert resp.status_code == 422

    def test_empty_features_422(self, client):
        resp = client.post("/predict", json={"features": []})
        assert resp.status_code == 422

    def test_missing_features_field_422(self, client):
        resp = client.post("/predict", json={})
        assert resp.status_code == 422

    def test_non_numeric_features_422(self, client):
        resp = client.post("/predict", json={"features": ["a"] * 30})
        assert resp.status_code == 422
