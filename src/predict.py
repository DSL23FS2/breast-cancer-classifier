"""Функция предсказания: загружает модель, возвращает label + probability."""
import joblib
from pathlib import Path
from typing import Sequence

from src.utils import get_logger

logger = get_logger(__name__)

_MODEL = None
MODEL_PATH = Path(__file__).parent.parent / "experiments" / "exp_0" / "trained_model.pkl"


def load_model(path: Path | None = None) -> None:
    """Загрузить модель в память (вызывается один раз при старте)."""
    global _MODEL
    model_path = path or MODEL_PATH
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}. Run 'python src/train.py' first."
        )
    _MODEL = joblib.load(model_path)
    logger.info(f"Model loaded from {model_path}")


def predict(features: Sequence[float]) -> dict:
    """
    Выполнить предсказание.

    Args:
        features: список из 30 числовых признаков Breast Cancer Wisconsin.

    Returns:
        dict: {
            "prediction": int,   # 0 = malignant, 1 = benign
            "probability": float # вероятность класса benign (1)
        }
    """
    global _MODEL
    if _MODEL is None:
        load_model()

    if len(features) != 30:
        raise ValueError(f"Expected 30 features, got {len(features)}")

    proba = _MODEL.predict_proba([features])[0]
    label = int(proba.argmax())
    probability = round(float(proba[1]), 4)  # P(benign)

    return {"prediction": label, "probability": probability}
