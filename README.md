# Breast Cancer Classifier

REST API для классификации злокачественности опухоли на основе датасета [Wisconsin Breast Cancer](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_breast_cancer.html).

Проект построен как учебный MLOps-контур с полным CI/CD циклом.

## Стек

| Слой | Технологии |
|------|-----------|
| ML | scikit-learn, DVC |
| API | FastAPI, uvicorn |
| Контейнеры | Docker, Docker Compose |
| CI/CD | Jenkins (JCasC + Job DSL) |
| Реестр образов | DockerHub |

## Версии проекта

| Версия | Что добавлено |
|--------|--------------|
| v1.0 | API + Jenkins CI/CD |
| v2.0 | + PostgreSQL |
| v3.0 | + Hashicorp Vault |
| v4.0 | + Apache Kafka |

---

## Быстрый старт

### Предусловия

- Docker Desktop запущен
- Git установлен
- Аккаунт на [DockerHub](https://hub.docker.com)
- Форк этого репозитория на GitHub

### 1. Клонировать репозиторий

```bash
git clone https://github.com/YOUR_USERNAME/breast-cancer-classifier.git
cd breast-cancer-classifier
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
```

Открыть `.env` и заполнить:

```env
GITHUB_REPO_URL=https://github.com/YOUR_USERNAME/breast-cancer-classifier.git
DOCKERHUB_USER=your_dockerhub_username
DOCKERHUB_PASS=your_dockerhub_password
JENKINS_ADMIN_PASSWORD=admin
```

### 3. Запустить

```bash
docker compose up -d --build
```

Первый запуск собирает образы — занимает 5–10 минут.

### 4. Проверить

| Сервис | Адрес |
|--------|-------|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Jenkins | http://localhost:8080 |

```bash
# Проверить API
curl http://localhost:8000/health
# {"status":"ok","model_loaded":true}
```

Jenkins UI: логин `admin`, пароль — значение `JENKINS_ADMIN_PASSWORD` из `.env`.

---

## CI/CD

### Как работает

После запуска Jenkins автоматически создаёт два пайплайна:

**`breast-cancer-ci`** — запускается при каждом push в ветку `develop`:
```
Checkout → Lint → DVC repro → Tests → Build Image → Push to DockerHub → Security Audit
```

**`breast-cancer-cd`** — запускается вручную или при push в `main`:
```
Checkout → Pull Image → Compose Up → Functional Tests
```

### Ветвление (GitFlow)

```
feature/* ──► develop ──► main
                           ↑
                      только через merge, никогда напрямую
```

| Ветка | Назначение |
|-------|-----------|
| `main` | Стабильный релиз. Прямые коммиты запрещены |
| `develop` | Рабочая ветка. Сюда идут все изменения |
| `feature/*` | Отдельные задачи, мержатся в `develop` |

### Добавить новую фичу

```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-feature

# ... делаем изменения ...

git add .
git commit -m "feat: описание"
git push origin feature/my-feature

# Merge в develop
git checkout develop
git merge --no-ff feature/my-feature
git push origin develop
```

---

## Локальный запуск API (без Docker)

```bash
# Создать виртуальное окружение
python -m venv .venv

# Активировать (Windows)
.venv\Scripts\activate
# Активировать (Linux/macOS)
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Воспроизвести ML-пайплайн (создаёт модель)
dvc repro

# Запустить API
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

API будет доступен на http://localhost:8000

---

## API

### `GET /health`

```json
{
  "status": "ok",
  "model_loaded": true
}
```

### `POST /predict`

**Запрос:**
```json
{
  "features": [17.99, 10.38, 122.8, 1001.0, 0.1184, 0.2776, 0.3001, 0.1471,
               0.2419, 0.07871, 1.095, 0.9053, 8.589, 153.4, 0.006399,
               0.04904, 0.05373, 0.01587, 0.03003, 0.006193, 25.38, 17.33,
               184.6, 2019.0, 0.1622, 0.6656, 0.7119, 0.2654, 0.4601, 0.1189]
}
```

30 числовых признаков датасета Wisconsin Breast Cancer.

**Ответ:**
```json
{
  "prediction": 0,
  "probability": 0.04,
  "label": "malignant"
}
```

`prediction`: `0` = злокачественная (malignant), `1` = доброкачественная (benign).

Интерактивная документация: http://localhost:8000/docs

---

## Пересборка

### Пересобрать только API

```bash
docker compose build api
docker compose up -d api
```

### Пересобрать Jenkins (после изменений в `jenkins/`)

```bash
docker compose build jenkins
docker compose up -d jenkins
```

### Полный перезапуск

```bash
docker compose down
docker compose up -d --build
```

> **Внимание:** `docker compose down` останавливает все сервисы.
> Данные Jenkins сохраняются в volume `jenkins-data` и не теряются.

### Сбросить Jenkins полностью (включая jobs и настройки)

```bash
docker compose down -v   # удаляет volumes
docker compose up -d --build
```

---

## Структура проекта

```
├── src/
│   ├── api.py              # FastAPI эндпоинты
│   ├── predict.py          # Загрузка модели и инференс
│   ├── preprocess.py       # Предобработка данных
│   ├── train.py            # Обучение модели
│   └── utils.py            # Утилиты
├── tests/
│   ├── test_api.py         # Интеграционные тесты
│   ├── test_predict.py     # Юнит-тесты
│   └── test_*.json         # Функциональные тесты (CD)
├── jenkins/
│   ├── Dockerfile          # Кастомный образ Jenkins
│   ├── casc.yaml           # Jenkins Configuration as Code
│   ├── plugins.txt         # Список плагинов
│   └── docker-entrypoint.sh
├── Dockerfile              # Образ API
├── docker-compose.yml      # Оркестрация сервисов
├── Jenkinsfile             # CI пайплайн
├── Jenkinsfile.cd          # CD пайплайн
├── dvc.yaml                # ML пайплайн
├── config.ini              # Конфигурация модели и интеграций
├── scenario.json           # Сценарий функциональных тестов
├── .env.example            # Шаблон переменных окружения
└── requirements.txt        # Python зависимости
```

---

## Устранение неполадок

| Проблема | Причина | Решение |
|----------|---------|---------|
| Jenkins не создал jobs | JCasC не применился | `Manage Jenkins → Configuration as Code → Reload` |
| CI: Push Image пропускается | Push не в `develop`/`main`/`release/*` | Проверить имя ветки |
| CD: API не отвечает | Контейнер не запустился | `docker compose logs api` |
| `dvc repro` падает локально | Не активировано `.venv` | Активировать перед запуском |
| `permission denied` на docker socket | GID mismatch после пересоздания | `docker compose restart jenkins` |
