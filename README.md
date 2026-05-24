# Breast Cancer Classifier

REST-сервис предсказания злокачественности опухоли на базе ML модели.

**Датасет**: [Breast Cancer Wisconsin](https://scikit-learn.org/stable/datasets/toy_dataset.html#breast-cancer-dataset)  
**Модель**: RandomForestClassifier  
**API**: FastAPI  
**Инфраструктура**: Docker · Jenkins · PostgreSQL · Vault · Kafka

---

## Быстрый старт

```bash
# Поднять весь контур
docker compose up -d

# API: http://localhost:8000
# Jenkins: http://localhost:8080
```

### Предсказание

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [17.99, 10.38, 122.8, 1001.0, 0.1184, 0.2776, 0.3001, 0.1471,
        0.2419, 0.07871, 1.095, 0.9053, 8.589, 153.4, 0.006399, 0.04904, 0.05373,
        0.01587, 0.03003, 0.006193, 25.38, 17.33, 184.6, 2019.0, 0.1622, 0.6656,
        0.7119, 0.2654, 0.4601, 0.1189]}'
```

---

## Разработка

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

make train      # обучить модель
make test       # запустить тесты
make up         # docker compose up
make down       # docker compose down
```

---

## Структура

```
src/        — исходный код (api, train, predict, preprocess, utils)
tests/      — pytest unit + integration тесты
notebooks/  — EDA и модель в Jupyter
experiments/— артефакты экспериментов (DVC-tracked)
data/       — датасеты (DVC-tracked)
jenkins/    — Jenkins как контейнер (JCasC)
vault/      — Hashicorp Vault конфиги (v3.0+)
```

---

## История версий

| Версия | Что добавлено |
|--------|---------------|
| v1.0 | ML pipeline + FastAPI + Docker + Jenkins CI/CD |
| v2.0 | PostgreSQL интеграция |
| v3.0 | Hashicorp Vault (секреты) |
| v4.0 | Apache Kafka (стриминг) |
