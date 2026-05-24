"""Подготовка данных: загрузка, разбивка, сохранение CSV."""
import pandas as pd
from pathlib import Path
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split

from src.utils import get_logger, read_config

logger = get_logger(__name__)


def load_and_split(config_path=None) -> dict:
    """
    Загрузить датасет, разбить на train/valid/test, сохранить CSV.

    Returns:
        dict с ключами: X_train, X_valid, X_test, y_train, y_valid, y_test,
                        feature_names, data_dir
    """
    cfg = read_config(config_path)
    random_state = cfg.getint("model", "random_state")
    test_size    = cfg.getfloat("model", "test_size")
    valid_size   = 0.25   # 25% от train_temp = 20% от всего → 60/20/20

    root = Path(__file__).parent.parent
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)

    logger.info("Loading Breast Cancer Wisconsin dataset...")
    raw = load_breast_cancer(as_frame=True)
    X = raw.data
    y = raw.target

    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    X_train, X_valid, y_train, y_valid = train_test_split(
        X_temp, y_temp, test_size=valid_size, random_state=random_state, stratify=y_temp
    )

    for name, X_part, y_part in [
        ("train", X_train, y_train),
        ("valid", X_valid, y_valid),
        ("test",  X_test,  y_test),
    ]:
        df = X_part.copy()
        df["label"] = y_part.values
        path = data_dir / f"breast_cancer_{name}.csv"
        df.to_csv(path, index=False)
        logger.info(f"Saved {name}: {len(df)} rows → {path}")

    # featured (все признаки + метка)
    featured = X.copy()
    featured["label"] = y.values
    featured.to_csv(data_dir / "breast_cancer_featured.csv", index=False)

    logger.info(f"Split: train={len(X_train)}, valid={len(X_valid)}, test={len(X_test)}")
    return dict(
        X_train=X_train, X_valid=X_valid, X_test=X_test,
        y_train=y_train, y_valid=y_valid, y_test=y_test,
        feature_names=list(X.columns),
        data_dir=data_dir,
    )


if __name__ == "__main__":
    load_and_split()
