"""Обучение модели: читает config.ini, тренирует, сохраняет в experiments/."""
import yaml
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score,
                              recall_score, f1_score, roc_auc_score)

from src.preprocess import load_and_split
from src.utils import get_logger, read_config

logger = get_logger(__name__)


def train(config_path=None) -> dict:
    """
    Обучить RandomForestClassifier и сохранить артефакты.

    Returns:
        dict с метриками тестовой выборки.
    """
    cfg = read_config(config_path)
    n_estimators = cfg.getint("model", "n_estimators")
    max_depth    = cfg.get("model", "max_depth", fallback="None")
    max_depth    = None if max_depth == "None" else int(max_depth)
    random_state = cfg.getint("model", "random_state")

    root = Path(__file__).parent.parent
    exp_dir = root / "experiments" / "exp_0"
    exp_dir.mkdir(parents=True, exist_ok=True)

    splits = load_and_split(config_path)
    X_train, y_train = splits["X_train"], splits["y_train"]
    X_test,  y_test  = splits["X_test"],  splits["y_test"]

    logger.info(f"Training RandomForestClassifier(n_estimators={n_estimators}, max_depth={max_depth})...")
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=random_state,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy":  round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred)), 4),
        "recall":    round(float(recall_score(y_test, y_pred)), 4),
        "f1":        round(float(f1_score(y_test, y_pred)), 4),
        "roc_auc":   round(float(roc_auc_score(y_test, y_prob)), 4),
    }

    model_path = exp_dir / "trained_model.pkl"
    joblib.dump(clf, model_path)
    logger.info(f"Model saved → {model_path}")

    metrics_path = exp_dir / "metrics.yml"
    with open(metrics_path, "w") as f:
        yaml.dump(metrics, f, default_flow_style=False)
    logger.info(f"Metrics: {metrics}")

    with open(exp_dir / "logs.txt", "a") as f:
        f.write(str(metrics) + "\n")

    assert metrics["accuracy"] >= 0.95, (
        f"Accuracy {metrics['accuracy']} < 0.95 — model quality check failed"
    )
    logger.info("✓ Accuracy >= 95%")
    return metrics


if __name__ == "__main__":
    train()
