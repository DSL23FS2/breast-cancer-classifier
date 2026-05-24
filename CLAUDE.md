# Breast Cancer Classifier — MLOps сервис

## О продукте

REST-сервис предсказания злокачественности опухоли (Breast Cancer Wisconsin dataset).  
Модель: RandomForestClassifier. API: FastAPI.

Лабораторные работы ИТМО — это **технические задания** на расширение этого продукта:

| ТЗ | Слой | Тег |
|----|------|-----|
| ЛР1 | ML pipeline + FastAPI + Docker + Jenkins | v1.0 |
| ЛР2 | Персистентность: PostgreSQL | v2.0 |
| ЛР3 | Безопасность: Hashicorp Vault | v3.0 |
| ЛР4 | Стриминг: Apache Kafka | v4.0 |

---

## Структура продукта

```
dev/                                 ← git root = продукт
├── CLAUDE.md
├── data/
│   ├── breast_cancer_orig.csv       ← исходный датасет (dvc-tracked)
│   ├── breast_cancer_train.csv
│   ├── breast_cancer_test.csv
│   ├── breast_cancer_valid.csv
│   └── breast_cancer_featured.csv
├── experiments/
│   └── exp_0/
│       ├── config.yml
│       ├── trained_model.pkl
│       ├── metrics.yml
│       └── logs.txt
├── notebooks/
│   ├── 01_eda_breast_cancer.ipynb
│   └── 02_model_breast_cancer.ipynb
├── src/
│   ├── preprocess.py                ← подготовка данных
│   ├── train.py                     ← обучение (читает config.ini → experiments/)
│   ├── predict.py                   ← predict(features) → {label, probability}
│   ├── utils.py                     ← логгирование, метрики
│   ├── api.py                       ← FastAPI: /predict, /health + startup hook интеграций
│   ├── db.py                        ← (v2.0) PostgreSQL: get_connection(), save_result()
│   ├── secrets.py                   ← (v3.0) Vault hvac: get_secret(path) → dict
│   ├── producer.py                  ← (v4.0) Kafka Producer: send_prediction(data)
│   └── consumer.py                  ← (v4.0) Kafka Consumer: consume loop → log
├── tests/
│   ├── test_predict.py              ← pytest unit тесты
│   ├── test_api.py                  ← pytest integration тесты
│   ├── test_0.json                  ← CD сценарий: benign
│   ├── test_1.json                  ← CD сценарий: malignant
│   └── test_2.json                  ← CD сценарий: /health
├── jenkins/                         ← (v1.0) Jenkins как контейнер в составе продукта
│   ├── Dockerfile                   ← jenkins:lts + Python 3.11 + DVC + Docker CLI
│   ├── plugins.txt                  ← плагины: git, pipeline, docker, blueocean, configuration-as-code
│   └── casc.yaml                    ← JCasC: агент, credentials (DockerHub), seed job
├── vault/                           ← (v3.0)
│   ├── config.hcl
│   ├── init.sh                      ← kv-v2 enable + kv put secret/db + secret/kafka
│   └── secrets.env.example
├── config.ini                       ← ВСЕ настройки:
│                                       [model] [api] [integrations] [database] [vault] [kafka]
├── .env.example                     ← DOCKERHUB_USER, DOCKERHUB_PASS (DB_PASSWORD → Vault в v3.0)
├── Dockerfile                       ← python:3.11-slim (API сервис)
├── docker-compose.yml               ← ЕДИНЫЙ DevOps-контур (см. ниже)
├── requirements.txt                 ← зависимости Docker образа + .venv
├── dev_sec_ops.yml                  ← хэши последних 5 коммитов (генерируется в CI)
├── scenario.json                    ← сценарий функционального тестирования CD
├── Makefile
├── Jenkinsfile                      ← CI: Checkout→Lint→Test→dvc repro→Build→Push DockerHub
├── Jenkinsfile.cd                   ← CD: Pull→Up→FunctionalTest→Down
├── dvc.yaml                         ← pipeline: preprocess → train → evaluate
├── .dvcignore
├── .gitignore
└── README.md
```

---

## Единый DevOps-контур

Все системы поднимаются одним `docker compose up`. Git (GitHub) — единственное исключение.

```
┌──────────────────────────────────────────────────────────────┐
│                    docker-compose network                     │
│                                                               │
│   ┌───────────┐    ┌──────────┐    ┌─────────────────────┐  │
│   │  jenkins  │    │   api    │    │   dvc-artifacts     │  │
│   │  :8080    │───►│  :8000   │    │   (named volume)    │  │
│   └───────────┘    └──────────┘    └─────────────────────┘  │
│        v1.0+            v1.0+                                 │
│   ┌───────────┐    ┌──────────┐    ┌────────┐  ┌────────┐  │
│   │ postgres  │    │  vault   │    │   zk   │  │ kafka  │  │
│   │  :5432    │    │  :8200   │    │  :2181 │  │  :9092 │  │
│   └───────────┘    └──────────┘    └────────┘  └────────┘  │
│        v2.0+            v3.0+           v4.0+                │
└──────────────────────────────────────────────────────────────┘
          ↕ /var/run/docker.sock
    [host Docker daemon]  — Jenkins собирает образы через него
```

**Эволюция `docker-compose.yml`:**
- `v1.0`: `api` + `jenkins` + named volume `dvc-artifacts`
- `v2.0`: + `postgres`
- `v3.0`: + `vault` (DB_PASSWORD уходит из `.env` в Vault)
- `v4.0`: + `zookeeper` + `kafka` + `consumer`

**Jenkins** (`jenkins/Dockerfile` ← `jenkins/jenkins:lts`):
- Python 3.11 + DVC + Docker CLI установлены в образ
- Монтирует `/var/run/docker.sock` для сборки Docker образов
- Конфигурируется через `jenkins/casc.yaml` (JCasC) — никакой ручной настройки
- `dvc repro` запускается как шаг CI pipeline

**DVC** — не отдельный сервис, инструмент внутри Jenkins:
- Jenkins pipeline вызывает `dvc repro` → артефакты в volume `dvc-artifacts`
- Volume монтируется в `api` контейнер при CD

---

## Архитектура интеграций

`config.ini` управляет активными слоями. `api.py` не меняется — только флаги:

```ini
[integrations]
database_enabled  = false   # → true в v2.0
vault_enabled     = false   # → true в v3.0
messaging_enabled = false   # → true в v4.0
```

```python
# api.py startup — единый шаблон для всех версий
@app.on_event("startup")
async def startup():
    cfg = read_config()
    if cfg["integrations"]["vault_enabled"]:
        from src.secrets import init_vault_client; init_vault_client()
    if cfg["integrations"]["database_enabled"]:
        from src.db import init_db; init_db()
    if cfg["integrations"]["messaging_enabled"]:
        from src.producer import init_producer; init_producer()
```

---

## Окружение

**Python**: 3.11  
**Виртуальная среда**: `.venv/` в корне `dev/` (в `.gitignore`)

```powershell
# Создать (один раз)
python -m venv .venv

# Активировать (Windows PowerShell)
.venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt
```

---

## GitFlow инструкция

### Схема
```
main     ●────────●────────●────────●
         ↑v1.0    ↑v2.0    ↑v3.0    ↑v4.0
develop ─●────────●────────●────────●──►
         ╲feat/*─►╱
          release/vX.Y
```

### Типы веток

| Ветка | От | В | Назначение |
|-------|----|---|------------|
| `feature/<name>` | `develop` | `develop` | атомарная задача |
| `release/vX.Y` | `develop` | `main` + `develop` | завершение ТЗ |
| `hotfix/<name>` | `main` | `main` + `develop` | срочный баг |

### Feature workflow
```bash
git checkout develop
git checkout -b feature/my-feature
# ... коммиты ...
git checkout develop
git merge --no-ff feature/my-feature
git branch -d feature/my-feature
```

### Release workflow
```bash
git checkout develop && git checkout -b release/v1.0
# только bagfix, без новых фич
git checkout main && git merge --no-ff release/v1.0
git tag v1.0
git checkout develop && git merge --no-ff release/v1.0
git branch -d release/v1.0
```

### Hotfix workflow
```bash
git checkout main && git checkout -b hotfix/fix-name
# исправить + тест
git checkout main && git merge --no-ff hotfix/fix-name
git tag v1.0.1                               # patch-тег
git checkout develop && git merge --no-ff hotfix/fix-name
git branch -d hotfix/fix-name
```
**Правило hotfix**: только баг, минимальный diff, никакой новой функциональности.

---

## Инструкция для каждой сессии

1. Активировать `.venv`: `.venv\Scripts\activate`
2. Прочитать этот CLAUDE.md — найти первую `[ ]` задачу в чеклисте
3. Создать feature-ветку: `git checkout develop && git checkout -b feature/<name>`
4. Выполнить задачу атомарно, закоммитить
5. Merge: `git checkout develop && git merge --no-ff feature/<name>`
6. Отметить `[x]` в чеклисте

---

## Чеклист задач

### Scaffold
- [x] **feature/project-scaffold** — `git init`, GitFlow init, все папки, README, `.gitignore`, `Makefile`, `config.ini` (все секции, интеграции = false)

### ML Pipeline (ТЗ ЛР1)
- [x] **feature/ml-pipeline** — EDA notebook, RandomForestClassifier ≥95% accuracy, `experiments/exp_0/`
- [x] **feature/python-scripts** — `preprocess.py`, `train.py`, `predict.py`, `utils.py`

### API Service (ТЗ ЛР1)
- [x] **feature/api-service** — FastAPI `/predict` + `/health`, startup hook, pydantic schemas
- [x] **feature/tests** — pytest unit + integration, `test_0-2.json`

### Версионирование данных (ТЗ ЛР1)
- [x] **feature/dvc-tracking** — `dvc init`, `dvc.yaml` pipeline, volume `dvc-artifacts`

### Контейнеризация (ТЗ ЛР1)
- [x] **feature/docker** — `Dockerfile` (api), `docker-compose.yml` v1 (api + jenkins + volumes), `requirements.txt`, `scenario.json`
- [x] **feature/jenkins-setup** — `jenkins/Dockerfile`, `jenkins/plugins.txt`, `jenkins/casc.yaml` (JCasC)

### CI/CD (ТЗ ЛР1)
- [x] **feature/ci-pipeline** — `Jenkinsfile`: Checkout→Lint→Test→`dvc repro`→Build→Push→`dev_sec_ops.yml`
- [x] **feature/cd-pipeline** — `Jenkinsfile.cd`: Pull→Up→FunctionalTest→Down

### → release/v1.0 (сдача ЛР1)
- [ ] merge develop→release/v1.0→main, `git tag v1.0`, ZIP, GitHub repo #1

---

### Персистентность (ТЗ ЛР2)
- [ ] **feature/postgres-compose** — `docker-compose.yml` +postgres:15, `init.sql`, healthcheck
- [ ] **feature/db-layer** — `src/db.py`: `get_connection()`, `init_db()`, `save_result()`
- [ ] **feature/api-persistence** — `config.ini` database_enabled=true; api + /predict подключают db
- [ ] **feature/env-credentials** — `.env.example` (DB_PASSWORD), `env_file` в compose
- [ ] **feature/cicd-v2** — Jenkinsfile тег v2.0, CD postgres healthcheck

### → release/v2.0 (сдача ЛР2)
- [ ] merge→main, `git tag v2.0`, GitHub fork #2

---

### Безопасность (ТЗ ЛР3)
- [ ] **feature/vault-compose** — `docker-compose.yml` +vault:1.15 dev mode, healthcheck
- [ ] **feature/vault-init** — `vault/config.hcl`, `vault/init.sh`, `secrets.env.example`
- [ ] **feature/secrets-layer** — `src/secrets.py`: `init_vault_client()`, `get_secret(path)`
- [ ] **feature/refactor-creds** — `config.ini` vault_enabled=true; db.py→secrets.py; убрать DB_PASSWORD
- [ ] **feature/cicd-v3** — Jenkinsfile тег v3.0, vault init.sh в CD

### → release/v3.0 (сдача ЛР3)
- [ ] merge→main, `git tag v3.0`, GitHub fork #3

---

### Стриминг (ТЗ ЛР4)
- [ ] **feature/kafka-compose** — `docker-compose.yml` +zookeeper+kafka, топик `model-predictions`
- [ ] **feature/producer-layer** — `src/producer.py`: `init_producer()`, `send_prediction(data)`
- [ ] **feature/consumer-service** — `src/consumer.py`: consume loop; сервис `consumer` в compose
- [ ] **feature/api-messaging** — `config.ini` messaging_enabled=true; api подключает producer
- [ ] **feature/cicd-v4** — Jenkinsfile тег v4.0, CD e2e kafka тест

### → release/v4.0 (сдача ЛР4)
- [ ] merge→main, `git tag v4.0`, GitHub fork #4

---

## Makefile цели

```makefile
make train      # python src/train.py
make test       # pytest tests/ -v --cov=src
make up         # docker compose up -d
make down       # docker compose down -v
make lint       # flake8 src/ tests/
make dvc-repro  # dvc repro
make zip        # ZIP дистрибутив для сдачи
```

---

## Верификация

| Версия | Проверка |
|--------|----------|
| v1.0 | `make up` → `curl localhost:8000/health` → `{"status":"ok"}`; Jenkins :8080 работает; образ на DockerHub |
| v2.0 | `/predict` → `docker exec postgres psql -U user -c "SELECT * FROM predictions"` → запись есть |
| v3.0 | нет `DB_PASSWORD` в compose/`.env`; `make up` работает; `vault kv get secret/db` → пароль |
| v4.0 | `/predict` → `docker logs consumer` → сообщение с результатом |
