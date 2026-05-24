"""FastAPI сервис предсказания злокачественности опухоли."""
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.predict import load_model, predict as run_predict
from src.utils import get_logger, read_config

logger = get_logger(__name__)


# ── Pydantic схемы ───────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    features: Annotated[
        list[float],
        Field(description="30 числовых признаков Breast Cancer Wisconsin")
    ]

    @field_validator("features")
    @classmethod
    def check_length(cls, v: list[float]) -> list[float]:
        if len(v) != 30:
            raise ValueError(f"Expected 30 features, got {len(v)}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "features": [
                    17.99, 10.38, 122.8, 1001.0, 0.1184, 0.2776, 0.3001, 0.1471,
                    0.2419, 0.07871, 1.095, 0.9053, 8.589, 153.4, 0.006399,
                    0.04904, 0.05373, 0.01587, 0.03003, 0.006193, 25.38, 17.33,
                    184.6, 2019.0, 0.1622, 0.6656, 0.7119, 0.2654, 0.4601, 0.1189
                ]
            }
        }
    }


class PredictResponse(BaseModel):
    prediction: int   = Field(description="0 = malignant, 1 = benign")
    probability: float = Field(description="P(benign)")
    label: str        = Field(description="'malignant' или 'benign'")


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: загрузить модель и активные интеграции."""
    cfg = read_config()

    # Vault — первым, так как другие зависят от него
    if cfg.getboolean("integrations", "vault_enabled", fallback=False):
        from src.secrets import init_vault_client
        init_vault_client()
        logger.info("Vault client initialized")

    # PostgreSQL
    if cfg.getboolean("integrations", "database_enabled", fallback=False):
        from src.db import init_db
        init_db()
        logger.info("Database initialized")

    # Kafka Producer
    if cfg.getboolean("integrations", "messaging_enabled", fallback=False):
        from src.producer import init_producer
        init_producer()
        logger.info("Kafka producer initialized")

    # Модель — всегда
    load_model()

    yield

    # Shutdown
    if cfg.getboolean("integrations", "messaging_enabled", fallback=False):
        from src.producer import close_producer
        close_producer()


# ── Приложение ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Breast Cancer Classifier",
    description="REST API для предсказания злокачественности опухоли (Breast Cancer Wisconsin).",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Проверка работоспособности сервиса."""
    from src.predict import _MODEL
    return HealthResponse(status="ok", model_loaded=_MODEL is not None)


@app.post("/predict", response_model=PredictResponse, tags=["Prediction"])
def predict(request: PredictRequest):
    """
    Предсказать злокачественность опухоли.

    - **prediction**: 0 = злокачественная (malignant), 1 = доброкачественная (benign)
    - **probability**: вероятность класса benign
    """
    try:
        result = run_predict(request.features)
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    label_map = {0: "malignant", 1: "benign"}

    # Персистентность (v2.0+)
    try:
        cfg = read_config()
        if cfg.getboolean("integrations", "database_enabled", fallback=False):
            from src.db import save_result
            save_result(
                features=request.features,
                prediction=result["prediction"],
                probability=result["probability"],
            )
    except Exception as e:
        logger.warning(f"DB save failed (non-critical): {e}")

    # Kafka (v4.0+)
    try:
        cfg = read_config()
        if cfg.getboolean("integrations", "messaging_enabled", fallback=False):
            from src.producer import send_prediction
            send_prediction({
                "features": request.features,
                "prediction": result["prediction"],
                "probability": result["probability"],
            })
    except Exception as e:
        logger.warning(f"Kafka send failed (non-critical): {e}")

    return PredictResponse(
        prediction=result["prediction"],
        probability=result["probability"],
        label=label_map[result["prediction"]],
    )
