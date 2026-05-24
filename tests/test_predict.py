"""Unit-тесты функции predict()."""
import pytest
from src.predict import predict, load_model

# Реальные записи из датасета (из sklearn breast_cancer)
MALIGNANT = [
    17.99, 10.38, 122.8, 1001.0, 0.1184, 0.2776, 0.3001, 0.1471,
    0.2419, 0.07871, 1.095, 0.9053, 8.589, 153.4, 0.006399,
    0.04904, 0.05373, 0.01587, 0.03003, 0.006193, 25.38, 17.33,
    184.6, 2019.0, 0.1622, 0.6656, 0.7119, 0.2654, 0.4601, 0.1189
]

BENIGN = [
    13.54, 14.36, 87.46, 566.3, 0.09779, 0.08129, 0.06664, 0.04781,
    0.1885, 0.05766, 0.2699, 0.7886, 2.058, 23.56, 0.008462,
    0.0146, 0.02387, 0.01315, 0.0198, 0.0023, 15.11, 19.26,
    99.7, 711.2, 0.144, 0.1773, 0.239, 0.1288, 0.2977, 0.07259
]


@pytest.fixture(autouse=True)
def ensure_model():
    """Гарантировать что модель загружена перед каждым тестом."""
    load_model()


class TestPredictOutput:
    def test_returns_dict(self):
        result = predict(MALIGNANT)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = predict(MALIGNANT)
        assert "prediction" in result
        assert "probability" in result

    def test_prediction_binary(self):
        for features in [MALIGNANT, BENIGN]:
            result = predict(features)
            assert result["prediction"] in (0, 1)

    def test_probability_range(self):
        for features in [MALIGNANT, BENIGN]:
            result = predict(features)
            assert 0.0 <= result["probability"] <= 1.0


class TestPredictValues:
    def test_malignant_prediction(self):
        result = predict(MALIGNANT)
        assert result["prediction"] == 0, "First record should be malignant (0)"

    def test_benign_prediction(self):
        result = predict(BENIGN)
        assert result["prediction"] == 1, "Benign sample should be predicted as 1"


class TestPredictValidation:
    def test_wrong_feature_count(self):
        with pytest.raises(ValueError, match="30 features"):
            predict([1.0] * 10)

    def test_empty_features(self):
        with pytest.raises(ValueError):
            predict([])

    def test_exact_30_features(self):
        result = predict([1.0] * 30)
        assert result["prediction"] in (0, 1)
