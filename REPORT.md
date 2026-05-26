# Отчёт: MLOps CI/CD — Breast Cancer Classifier

## Оглавление

1. [Обзор проекта и архитектура](#1-обзор-проекта-и-архитектура)
2. [GitFlow — стратегия ветвления](#2-gitflow--стратегия-ветвления)
3. [Структура репозитория](#3-структура-репозитория)
4. [DVC — версионирование ML-пайплайна](#4-dvc--версионирование-ml-пайплайна)
5. [Docker — контейнеризация](#5-docker--контейнеризация)
6. [Docker Compose — оркестрация сервисов](#6-docker-compose--оркестрация-сервисов)
7. [Jenkins — настройка через JCasC и Job DSL](#7-jenkins--настройка-через-jcasc-и-job-dsl)
8. [CI-пайплайн (Jenkinsfile)](#8-ci-пайплайн-jenkinsfile)
9. [CD-пайплайн (Jenkinsfile.cd)](#9-cd-пайплайн-jenkinsfilecd)
10. [Решённые проблемы и их причины](#10-решённые-проблемы-и-их-причины)
11. [Инварианты — почему не другие решения](#11-инварианты--почему-не-другие-решения)
12. [Воспроизведение с нуля](#12-воспроизведение-с-нуля)

---

## 1. Обзор проекта и архитектура

### Продукт

REST API для классификации злокачественности опухоли (датасет Wisconsin Breast Cancer).  
Стек: **Python 3.11 + FastAPI + scikit-learn + DVC + Docker + Jenkins**.

### Компоненты инфраструктуры

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Host (Windows)                 │
│                                                          │
│  ┌──────────────────┐    ┌──────────────────────────┐   │
│  │   bc-jenkins     │    │       bc-api             │   │
│  │  Jenkins LTS     │    │   FastAPI + uvicorn      │   │
│  │  :8080 / :50000  │    │       :8000              │   │
│  │                  │    │                          │   │
│  │  CI Pipeline     │    │  /health → {"status":    │   │
│  │  CD Pipeline     │    │    "ok","model_loaded":  │   │
│  │                  │    │    true}                 │   │
│  └──────────────────┘    └──────────────────────────┘   │
│           │                          │                   │
│           └──────────────────────────┘                   │
│                    app-network (bridge)                   │
└─────────────────────────────────────────────────────────┘
          │ push                 │ pull latest
          ▼                      │
   ┌──────────────┐              │
   │  DockerHub   │◄─────────────┘
   │ kingfigmaboy/│
   │ breast-cancer│
   │ -api:latest  │
   └──────────────┘
          ▲
   CI пушит образ после
   успешных тестов
```

### Поток данных

```
GitHub (develop) ──SCM poll──► Jenkins CI ──► DVC repro ──► pytest ──► docker build ──► push :latest
                                                                                              │
GitHub (main)    ──SCM poll──► Jenkins CD ──► docker pull :latest ──► compose up ──► functional tests
```

---

## 2. GitFlow — стратегия ветвления

### Модель

```
main ────────────────────────────────────────────────────────►  (стабильные релизы)
       ╲                     ╲
        ╲ merge               ╲ merge
         ╲                     ╲
develop ──────────────────────────────────────────────────────►  (рабочая ветка)
          ╲          ╲
           feature/*  feature/*   (отдельные задачи)
```

### Правила

| Ветка | Назначение | Кто пишет | Куда мержит |
|-------|-----------|-----------|-------------|
| `main` | Стабильный продакшн | Никто напрямую | — |
| `develop` | Интеграция фич | Разработчики через PR/merge | `main` через release |
| `feature/*` | Отдельная фича | Разработчик | `develop` |
| `release/*` | Финальная подготовка | Тех. лид | `main` + `develop` |
| `hotfix/*` | Срочный фикс продакшна | Разработчик | `main` + `develop` |

### Критические правила

1. **НИКОГДА прямых коммитов в `main`** — только merge из `release/*` или `hotfix/*`
2. **НИКОГДА обратных мержей `main` → `develop`** — только `develop` → `main`
3. Все исправления идут в `develop`, затем мержатся в `main` через release-commit

### Почему GitFlow, а не trunk-based development?

Trunk-based предполагает частые маленькие коммиты прямо в `main` с feature-flags. GitFlow выбран потому что:
- Учебная среда с явными версиями (ЛР1, ЛР2, ЛР3, ЛР4)
- CI запускается на `develop`, CD — только на `main`; нужна чёткая граница
- Trunk-based требует зрелой культуры тестирования и feature-flags — лишняя сложность

---

## 3. Структура репозитория

```
breast-cancer-classifier/
├── src/
│   ├── api.py            # FastAPI приложение (endpoints)
│   ├── predict.py        # Загрузка модели и инференс
│   ├── preprocess.py     # Предобработка данных
│   ├── train.py          # Обучение модели
│   └── utils.py          # Утилиты
├── tests/
│   ├── test_api.py       # Интеграционные тесты FastAPI
│   ├── test_predict.py   # Юнит-тесты инференса
│   ├── test_0.json       # Функциональный тест: predict malignant
│   ├── test_1.json       # Функциональный тест: predict benign
│   └── test_2.json       # Функциональный тест: health check
├── jenkins/
│   ├── Dockerfile        # Кастомный образ Jenkins
│   ├── casc.yaml         # JCasC конфигурация
│   ├── plugins.txt       # Список плагинов
│   └── docker-entrypoint.sh  # Runtime-фикс docker socket
├── data/                 # CSV-файлы (DVC, не Git)
├── experiments/
│   └── exp_0/
│       ├── trained_model.pkl  # Модель (DVC cache)
│       └── metrics.yml        # Метрики (git-tracked)
├── Dockerfile            # Образ API-сервиса
├── docker-compose.yml    # Оркестрация
├── Jenkinsfile           # CI-пайплайн
├── Jenkinsfile.cd        # CD-пайплайн
├── dvc.yaml              # DVC пайплайн
├── scenario.json         # Сценарий функциональных тестов
├── config.ini            # Конфигурация модели
├── requirements.txt      # Python-зависимости
├── .gitattributes        # Нормализация окончаний строк
└── .gitignore            # Исключения Git
```

### .gitattributes — почему обязателен на Windows

```gitattributes
*.sh        text eol=lf
*.yaml      text eol=lf
*.yml       text eol=lf
Dockerfile* text eol=lf
Jenkinsfile* text eol=lf
```

**Проблема**: Windows git по умолчанию конвертирует `LF → CRLF` при checkout.  
Bash-скрипты с `CRLF` внутри Linux-контейнера не запускаются: shebang `#!/bin/bash\r` не распознаётся ядром.

**Решение**: `.gitattributes` принудительно хранит эти файлы в репозитории с `LF`.  
Дополнительно в `jenkins/Dockerfile`:
```dockerfile
RUN sed -i 's/\r$//' /docker-entrypoint.sh
```
Это fallback для случаев, когда `.gitattributes` не сработал (например, файл уже был закоммичен с CRLF до добавления атрибутов).

### .gitignore — ключевые исключения

```gitignore
.env                        # Секреты — никогда в Git
vault/secrets.env           # Секреты Vault
data/*.csv                  # DVC управляет данными
experiments/*/trained_model.pkl  # DVC управляет моделью
.venv/                      # Виртуальное окружение
```

**Почему `data/*.csv` в gitignore**: DVC и Git не должны одновременно отслеживать одни файлы. Если файл есть в `git` и в `dvc.yaml` как output — DVC выдаёт ошибку конфликта при `dvc repro`.

---

## 4. DVC — версионирование ML-пайплайна

### Зачем DVC

Модели и датасеты — бинарные файлы размером от сотен МБ. Git не предназначен для бинарников: каждая новая версия модели удваивает размер репозитория. DVC хранит в Git только метаданные (хэши), а сами файлы — в отдельном хранилище (локальный кэш, S3, GCS и т.д.).

### dvc.yaml — пайплайн

```yaml
stages:
  preprocess:
    cmd: python src/preprocess.py
    deps:
      - src/preprocess.py
      - src/utils.py
      - config.ini
    outs:
      - data/breast_cancer_train.csv
      - data/breast_cancer_valid.csv
      - data/breast_cancer_test.csv
      - data/breast_cancer_featured.csv

  train:
    cmd: python src/train.py
    deps:
      - src/train.py
      - src/preprocess.py
      - src/utils.py
      - config.ini
      - data/breast_cancer_train.csv
      - data/breast_cancer_test.csv
    outs:
      - experiments/exp_0/trained_model.pkl:
          cache: true
    metrics:
      - experiments/exp_0/metrics.yml:
          cache: false

  evaluate:
    cmd: python -c "import yaml; m=yaml.safe_load(open('experiments/exp_0/metrics.yml')); assert m['accuracy']>=0.95, ..."
    deps:
      - experiments/exp_0/metrics.yml
```

### Ключевые решения в dvc.yaml

**`cache: true` для модели, `cache: false` для метрик**

- `trained_model.pkl` с `cache: true`: DVC хранит файл в `.dvc/cache`, версионирует его, не кладёт в git. При `dvc repro` пересоздаётся только если изменились deps.
- `metrics.yml` с `cache: false`: файл метрик маленький, нужно видеть его историю в git (`git log`), поэтому он отслеживается git-ом, а DVC только объявляет его как метрику.

**`dvc repro --no-commit`**

Флаг `--no-commit` запускает все стадии, но **не записывает** результат в dvc cache. Причина: в CI у нас нет настроенного remote-хранилища DVC. Без флага команда пытается сохранить в кэш, затем падает при отсутствии remote. `--no-commit` позволяет воспроизвести пайплайн и получить артефакты (модель, метрики) в workspace, не сохраняя их в DVC storage.

**Почему evaluate использует однострочный Python, а не отдельный скрипт**

Изначально использовался YAML folded-scalar (оператор `>`), который добавляет пробел в начало строки Python-кода, что вызывало `IndentationError`. Однострочная команда с `;` надёжно работает без проблем с форматированием YAML.

**Почему `breast_cancer_orig.csv` нет в outputs preprocess**

Скрипт `preprocess.py` не создаёт этот файл — он работает со встроенным датасетом scikit-learn. Если объявить несуществующий output в `dvc.yaml`, `dvc repro` падает с ошибкой: "output was not created by the pipeline".

---

## 5. Docker — контейнеризация

### Dockerfile API-сервиса

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config.ini .
COPY experiments/ ./experiments/

EXPOSE 8000
ENV PYTHONPATH=/app
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Почему `python:3.11-slim`**: slim-вариант не содержит dev-инструментов и документации; экономит ~300 МБ относительно полного образа. Версия `3.11` зафиксирована — плавающий тег `latest` мог бы сломать пайплайн при выходе Python 3.13 с несовместимыми изменениями.

**Почему `requirements.txt` копируется отдельно от кода**: Docker кэширует слои. Если код изменился, а зависимости нет — Docker не запускает `pip install` заново, используя кэш. Это ускоряет билд в 3–10 раз.

**Почему `--no-install-recommends` и `rm -rf /var/lib/apt/lists/*`**: уменьшает размер образа. apt устанавливает рекомендуемые пакеты по умолчанию; `--no-install-recommends` берёт только необходимое. Очистка `/var/lib/apt/lists/` убирает индексы пакетов, которые больше не нужны.

**Почему `EXPOSE 8000` не публикует порт**: `EXPOSE` — документация, не фактическое открытие порта. Реальное открытие — в `docker-compose.yml` через `ports: "8000:8000"`. Без `docker-compose` для открытия нужен `-p 8000:8000` при `docker run`.

### jenkins/Dockerfile

```dockerfile
FROM jenkins/jenkins:lts

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip curl git gosu \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/local/bin/python

RUN pip install --no-cache-dir --break-system-packages dvc

RUN curl -fsSL https://get.docker.com | sh

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

COPY casc.yaml /var/jenkins_home/casc.yaml
RUN chown jenkins:jenkins /var/jenkins_home/casc.yaml

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
ENV CASC_JENKINS_CONFIG="/var/jenkins_home/casc.yaml"

ENTRYPOINT ["/docker-entrypoint.sh"]
```

**Почему `USER root` и нет финального `USER jenkins`**: Jenkins должен стартовать через `docker-entrypoint.sh`, который выполняется от root, чтобы исправить права docker socket. Entrypoint сам делает `exec gosu jenkins` в конце — переключает процесс на jenkins-пользователя. Если поставить `USER jenkins` в Dockerfile, entrypoint не сможет работать с сокетом.

**Почему `gosu`, а не `su` или `sudo`**:
- `su jenkins -c "..."` запускает новый shell, теряет сигналы (SIGTERM и т.д.) — Jenkins не сможет корректно завершиться
- `sudo` требует настройки sudoers, усложняет образ
- `gosu` делает именно то, что нужно: `exec`-ом заменяет текущий процесс (root → jenkins), сохраняя PID 1 и правильную передачу сигналов

**Почему `curl -fsSL https://get.docker.com | sh`**: официальный скрипт установки Docker от Docker Inc. устанавливает только Docker CLI — то, что нужно Jenkins для выполнения `docker build/push`. Внутри контейнера работает Docker-in-Docker через проброс `/var/run/docker.sock` (см. docker-compose).

**Почему `--break-system-packages` для pip**: В Debian Trixie (основа jenkins:lts) pip по умолчанию запрещает установку в системный Python — `externally-managed-environment`. Флаг снимает ограничение. Альтернативой был бы `python -m venv` для DVC, но это усложняет Dockerfile и пайплайн. В контейнере нет пользовательских Python-проектов, которые могли бы сломаться — флаг безопасен.

### docker-entrypoint.sh

```bash
#!/bin/bash
set -e

if [ -S /var/run/docker.sock ]; then
    SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    if [ "$SOCK_GID" = "0" ]; then
        # Docker Desktop (Windows/macOS): socket принадлежит root
        # groupmod -g 0 невозможен — группа 0 уже существует (root)
        # Решение: открыть сокет всем пользователям
        chmod 666 /var/run/docker.sock
    else
        # Linux: socket имеет специальную docker-группу
        # Подстраиваем GID контейнерной docker-группы под GID хоста
        CUR_GID=$(getent group docker | cut -d: -f3)
        if [ "$SOCK_GID" != "$CUR_GID" ]; then
            groupmod -g "$SOCK_GID" docker
        fi
        usermod -aG docker jenkins
    fi
fi

exec gosu jenkins /bin/tini -- /usr/local/bin/jenkins.sh "$@"
```

**Почему `chmod 666` для Docker Desktop**: Docker Desktop на Windows/macOS прокидывает docker socket с GID=0 (root). Невозможно добавить пользователя в группу с GID=0 (это группа root). Единственный выход — разрешить чтение/запись всем пользователям. В изолированной среде разработки это приемлемо. На production Linux-хосте GID≠0, поэтому ветка с `groupmod` обеспечивает безопасный вариант.

**Почему читаем GID в runtime, а не hardcode**: GID docker-группы на хосте зависит от дистрибутива и конфигурации. На Ubuntu типично GID=999, но может быть любым. Hardcode сломается на другом хосте. Runtime-чтение через `stat -c '%g'` универсально.

**Почему `exec gosu jenkins /bin/tini -- /usr/local/bin/jenkins.sh`**: 
- `exec` заменяет процесс entrypoint на Jenkins (не fork, а замена) — Jenkins получает PID 1
- `/bin/tini` — init-процесс, собирает зомби-процессы и правильно пробрасывает сигналы в Jenkins
- Без `tini` при `docker stop` Jenkins получает SIGTERM → 10 сек ожидания → SIGKILL, что приводит к повреждению workspace

---

## 6. Docker Compose — оркестрация сервисов

### docker-compose.yml — ключевые решения

```yaml
name: bc          # ← обязательно здесь, не в .env!

services:
  api:
    build: .
    image: ${DOCKERHUB_USER:-local}/breast-cancer-api:${IMAGE_TAG:-latest}
    container_name: bc-api
    ports:
      - "8000:8000"
    volumes:
      - dvc-artifacts:/app/experiments
    networks:
      - app-network
    restart: unless-stopped

  jenkins:
    build: ./jenkins
    image: ${DOCKERHUB_USER:-local}/breast-cancer-jenkins:${IMAGE_TAG:-latest}
    container_name: bc-jenkins
    ports:
      - "8080:8080"
      - "50000:50000"
    volumes:
      - jenkins-data:/var/jenkins_home
      - /var/run/docker.sock:/var/run/docker.sock   # Docker-out-of-Docker
      - dvc-artifacts:/dvc-artifacts
      - .:/workspace:ro
    env_file:
      - path: .env
        required: false
    environment:
      - CASC_JENKINS_CONFIG=/var/jenkins_home/casc.yaml
      - JAVA_OPTS=-Djenkins.install.runSetupWizard=false ...
    networks:
      - app-network
    restart: unless-stopped

volumes:
  jenkins-data:
  dvc-artifacts:

networks:
  app-network:
    driver: bridge
```

### Почему `name: bc` должен быть в `docker-compose.yml`, а не в `.env`

Docker Compose использует имя проекта как **prefix для контейнеров и как идентификатор для управления ими**.

Проблема: переменная `COMPOSE_PROJECT_NAME` в `.env` работает только когда compose запускается из той же директории с тем же `.env`. Если compose запускается из Jenkins (другой рабочий каталог, другой env) — он не находит `.env` и использует имя директории (например, `dev`). В итоге контейнер `bc-api`, созданный вручную из проекта `bc`, и контейнер, которым управляет CD-пайплайн из проекта `dev`, — **разные контейнеры с одинаковым именем**. Отсюда конфликт: `Container bc-api already in use`.

`name: bc` в `docker-compose.yml` встроен в файл конфигурации — читается всегда, в любом контексте, независимо от переменных окружения.

### Почему `restart: unless-stopped`

- `always`: перезапускает при любом выходе, даже при `docker stop` — неудобно для разработки
- `on-failure`: перезапускает только при ненулевом exit-коде — не защищает от аварийного завершения хоста
- `unless-stopped`: перезапускает всегда, кроме явного `docker stop` — оптимальный баланс

### Почему Docker-out-of-Docker (DoD), а не Docker-in-Docker (DinD)

**DinD** (`--privileged`): запускает полноценный Docker-демон внутри контейнера. Проблемы: требует `--privileged` (root на хосте), образы не разделяются с хостом (двойная трата места), сложная изоляция.

**DoD** (проброс `/var/run/docker.sock`): Jenkins использует Docker-демон хоста через unix-сокет. Образы видны и на хосте, и в Jenkins. Более простой, более используемый подход в учебных и dev-средах. Единственный риск: Jenkins имеет доступ к docker-демону хоста — в production это ограничивается через авторизацию или rootless Docker.

### Почему `dvc-artifacts` volume, а не bind mount

```yaml
volumes:
  - dvc-artifacts:/app/experiments
```

Bind mount (`.:/app/experiments`) привязал бы контейнер к конкретному пути хоста — непортируемо. Docker volume управляется Docker-ом, не зависит от структуры хоста. При уничтожении и пересоздании контейнера данные сохраняются в volume.

---

## 7. Jenkins — настройка через JCasC и Job DSL

### Почему JCasC (Jenkins Configuration as Code)

Традиционный Jenkins требует ручной настройки через UI: создание пользователей, credentials, jobs. Это:
- Не воспроизводимо (настройки хранятся в XML в `/var/jenkins_home`)
- Не версионируемо
- Требует ручного повтора при пересоздании контейнера

JCasC (`configuration-as-code` плагин) читает `casc.yaml` при старте и полностью конфигурирует Jenkins. Всё в коде, всё в Git.

### casc.yaml — структура

```yaml
jenkins:
  systemMessage: "Breast Cancer Classifier — CI/CD"
  numExecutors: 2
  securityRealm:
    local:
      allowsSignup: false
      users:
        - id: "admin"
          password: "${JENKINS_ADMIN_PASSWORD:-admin}"
  authorizationStrategy:
    loggedInUsersCanDoAnything:
      allowAnonymousRead: false

credentials:
  system:
    domainCredentials:
      - credentials:
          - usernamePassword:
              scope: GLOBAL
              id: "dockerhub-credentials"
              username: "${DOCKERHUB_USER:-local}"
              password: "${DOCKERHUB_PASS:-}"
              description: "DockerHub credentials"

jobs:
  - script: |
      pipelineJob('breast-cancer-ci') {
        definition {
          cpsScm {
            scm {
              git {
                remote { url('https://github.com/...') }
                branch('*/develop')
              }
            }
            scriptPath('Jenkinsfile')
          }
        }
        triggers { scm('H/5 * * * *') }
      }

      pipelineJob('breast-cancer-cd') {
        definition {
          cpsScm {
            scm {
              git {
                remote { url('https://github.com/...') }
                branch('*/main')
              }
            }
            scriptPath('Jenkinsfile.cd')
          }
        }
      }
```

### Почему Job DSL, а не XML/Pipeline Library

Jenkins хранит конфигурацию jobs в XML (`config.xml`). JCasC не умеет создавать jobs напрямую — только настраивать систему. Job DSL — Groovy DSL для создания jobs программно. Это наиболее идиоматичный способ создать jobs через JCasC (через секцию `jobs`).

### Почему CI опрашивает `*/develop`, а CD — `*/main`

CI (Jenkinsfile) запускает тяжёлые операции: lint, тесты, DVC repro, docker build. Это должно происходить на каждый push в `develop` — рабочую ветку. Если тесты падают, разработчик узнаёт немедленно.

CD (Jenkinsfile.cd) деплоит на "production" (localhost в учебном контексте). Деплоить нужно только стабильный код из `main`. Запуск CD на каждый коммит в `develop` означал бы деплой незавершённого кода.

### Почему у CI есть SCM polling (`H/5 * * * *`), а у CD нет

`H/5 * * * *` — каждые 5 минут (с хэшированием по имени задачи, чтобы не перегружать Jenkins в момент `*/5`). CD не нужен автоматический триггер в учебном контексте — запускается вручную или через webhook GitHub (не настроен). Добавить триггер в CD легко, но для лабораторной работы ручной запуск достаточен.

### plugins.txt — минимальный набор

```
git                   # Работа с Git-репозиториями
pipeline-stage-view   # Визуализация стадий в UI
workflow-aggregator   # Declarative Pipeline DSL
docker-workflow        # docker.image(), withRegistry() в пайплайне
docker-plugin          # Интеграция с Docker для агентов
configuration-as-code  # JCasC
job-dsl               # Job DSL для создания jobs
credentials           # Хранилище секретов
credentials-binding   # Binding секретов в environment
git-client            # Git low-level operations
github                # GitHub интеграция (webhooks, status)
pipeline-github-lib   # Shared libraries
timestamper           # Временные метки в логах
ws-cleanup            # cleanWs() в post
```

Принцип: только то, что используется. Лишние плагины замедляют старт, увеличивают поверхность атаки, могут конфликтовать друг с другом.

---

## 8. CI-пайплайн (Jenkinsfile)

### Полный пайплайн

```
Checkout → Setup → Lint → DVC repro → Test → Build Image → Push Image → Security Audit
```

### Environment блок

```groovy
environment {
    DOCKERHUB_CREDS = credentials('dockerhub-credentials')
    IMAGE_NAME      = "${DOCKERHUB_CREDS_USR}/breast-cancer-api"
    IMAGE_TAG       = "${env.BUILD_NUMBER}"
    PYTHONPATH      = "${env.WORKSPACE}"
}
```

**Почему `credentials()` binding**: Плагин `credentials-binding` автоматически:
1. Достаёт секрет из Jenkins Credentials Store
2. Создаёт переменные `DOCKERHUB_CREDS_USR` и `DOCKERHUB_CREDS_PSW`
3. **Маскирует** значение `DOCKERHUB_CREDS_PSW` в логах — заменяет на `****`
4. Очищает переменные после завершения блока

Альтернатива — хранить пароль в `.env` и читать вручную — небезопасна: значение попадает в логи, файл `.env` может оказаться в Git.

**Почему `IMAGE_TAG = BUILD_NUMBER`**: Уникальный тег для каждого билда. Позволяет откатиться к конкретному билду: `docker pull kingfigmaboy/breast-cancer-api:4`. Альтернативы:
- `git rev-parse --short HEAD` (commit hash) — понятнее для разработчика, сложнее для ops
- `$(date +%Y%m%d%H%M%S)` — нечитаемо в UI
- `BUILD_NUMBER` — простой монотонно возрастающий счётчик, достаточен для учебного контекста

### Порядок стадий — почему DVC repro ПЕРЕД тестами

```
Stage('DVC repro')  ← должен быть ДО Test
Stage('Test')
```

Тесты (`test_api.py`, `test_predict.py`) импортируют модель из `experiments/exp_0/trained_model.pkl`. Если `dvc repro` не был запущен, модели нет — все тесты падают с `FileNotFoundError`. Правило: сначала создаём артефакты, затем тестируем.

### DVC repro в Jenkins

```groovy
sh 'PATH=$PWD/.venv/bin:$PATH dvc repro --no-commit'
```

`PATH=$PWD/.venv/bin:$PATH` — prepend пути к virtualenv без его активации. `source .venv/bin/activate` работает только в интерактивном shell, в `sh` не работает. Prepend PATH — правильный способ использовать venv в скриптах.

### Push Image — почему `GIT_BRANCH`, а не `branch 'develop'`

```groovy
when {
    anyOf {
        expression { env.GIT_BRANCH ==~ /.*\/develop/ }
        expression { env.GIT_BRANCH ==~ /.*\/main/ }
        expression { env.GIT_BRANCH ==~ /.*\/release\/.+/ }
    }
}
```

В Jenkins есть два типа jobs:
- **Multibranch Pipeline**: автоматически создаёт job на каждую ветку, переменная `BRANCH_NAME = "develop"` (без prefix)
- **Regular Pipeline** (используем мы): одна job, подписанная на конкретную ветку. Переменная `GIT_BRANCH = "origin/develop"` (с prefix remote-name)

`when { branch 'develop' }` проверяет `BRANCH_NAME`, которого в regular pipeline нет — всегда пропускает стадию. Regex `/.*\/develop/` матчит `origin/develop` корректно.

### Почему двойной push (с тегом и latest)

```groovy
docker push ${IMAGE_NAME}:${IMAGE_TAG}   // :4 — конкретная версия
docker push ${IMAGE_NAME}:latest         // :latest — для CD
```

CD-пайплайн всегда тянет `latest` — простой и предсказуемый. Нумерованный тег даёт историю и возможность отката.

### Почему `docker logout` после push

Credentials хранятся в `~/.docker/config.json` в plaintext. `docker logout` удаляет токен после push. Jenkins workspace может быть доступен другим jobs — logout снижает риск утечки.

### Security Audit stage

```groovy
sh '''
    echo "# dev_sec_ops.yml — last 5 commits SHA" > dev_sec_ops.yml
    git log --pretty=format:"  - sha: %H..." -5 >> dev_sec_ops.yml
'''
archiveArtifacts artifacts: 'dev_sec_ops.yml', fingerprint: true
```

Создаёт артефакт с SHA последних 5 коммитов. `fingerprint: true` — Jenkins вычисляет MD5 артефакта и отслеживает, какой билд его создал. Используется для аудита: "какой код был задеплоен в этом билде".

### `cleanWs()` в post always

```groovy
post {
    always { cleanWs() }
}
```

Очищает workspace после каждого билда. Причина: Docker-образы, `.venv`, DVC cache — занимают гигабайты. Без очистки Jenkins-контейнер быстро исчерпает место. Плагин `ws-cleanup` делает это безопасно, не удаляя Jenkins-конфигурацию.

---

## 9. CD-пайплайн (Jenkinsfile.cd)

### Назначение

CD не пересобирает образ и не запускает тесты кода. Его задача:
1. Взять готовый образ из DockerHub (артефакт CI)
2. Запустить его
3. Проверить, что сервис работает корректно (функциональные тесты)

Это разделение ответственности: CI отвечает за качество кода, CD — за корректность деплоя.

### Environment

```groovy
environment {
    DOCKERHUB_CREDS      = credentials('dockerhub-credentials')
    COMPOSE_PROJECT_NAME = "bc"
    BASE_URL             = "http://api:8000"
    SCENARIO_FILE        = "scenario.json"
}
```

**Почему `http://api:8000`, а не `http://localhost:8000`**:

Jenkins запущен внутри контейнера `bc-jenkins`. Когда Jenkins выполняет `curl http://localhost:8000/health`, `localhost` резолвится в сетевой интерфейс самого контейнера `bc-jenkins`. API работает в другом контейнере `bc-api`.

Оба контейнера подключены к сети `app-network`. Docker автоматически создаёт DNS-запись по имени сервиса: контейнер `api` доступен по имени `api` внутри сети. Поэтому корректный адрес — `http://api:8000`.

**Почему `COMPOSE_PROJECT_NAME = "bc"` здесь, если уже есть `name: bc` в docker-compose.yml**:

`name: bc` в `docker-compose.yml` — основной источник истины. Переменная в environment — дополнительная подстраховка для edge-cases, когда compose не может прочитать файл. На практике `name: bc` в файле достаточно.

### Stage: Pull Image

```groovy
sh """
    echo "${DOCKERHUB_CREDS_PSW}" | docker login -u "${DOCKERHUB_CREDS_USR}" --password-stdin
    docker pull ${DOCKERHUB_CREDS_USR}/breast-cancer-api:latest
    docker logout
"""
```

**Почему `--password-stdin`, а не `-p ${PASSWORD}`**: При передаче пароля аргументом он виден в `ps aux` и попадает в shell history. `--password-stdin` читает пароль из stdin — безопаснее, и Jenkins маскирует его в логах.

**Зачем делать `docker pull` если уже есть `compose up`**: Явный `docker pull` гарантирует свежую версию до запуска. `docker compose up` без явного pull может использовать локально кэшированный образ. Явный pull + явный login — более надёжная и контролируемая последовательность.

### Stage: Compose Up

```groovy
sh """
    DOCKERHUB_USER=${DOCKERHUB_CREDS_USR} docker compose up -d --force-recreate api
"""
```

**Почему `--force-recreate`**: Без этого флага compose проверяет: изменилась ли конфигурация контейнера? Если нет — оставляет старый. Но образ мог обновиться (новый `latest`). `--force-recreate` принудительно пересоздаёт контейнер с новым образом, даже если конфигурация не изменилась.

**Почему запускаем только `api`, а не весь compose**: Команда `docker compose up -d` без указания сервиса запустила бы все сервисы, включая Jenkins. Это создало бы второй экземпляр Jenkins — конфликт по порту 8080. Явное указание `api` поднимает только нужный сервис.

**Почему `DOCKERHUB_USER=...` как inline переменная**: `docker-compose.yml` использует `${DOCKERHUB_USER:-local}` для имени образа. Эта переменная не задана в environment Jenkins по умолчанию. Inline-передача перед командой устанавливает переменную только для этого вызова — минимальная область видимости.

### Health check loop

```groovy
sh '''
    for i in $(seq 1 30); do
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" ${BASE_URL}/health || echo "000")
        if [ "$STATUS" = "200" ]; then exit 0; fi
        sleep 3
    done
    docker compose logs api
    exit 1
'''
```

**Почему 30 попыток × 3 сек = 90 сек**: uvicorn запускается быстро (~1-2 сек), но модель scikit-learn загружается из файла — может занять несколько секунд. 90 секунд с запасом.

**Почему `-o /dev/null -w "%{http_code}"`**: Нам нужен только HTTP status code, не тело ответа. `-o /dev/null` выбрасывает тело, `-w "%{http_code}"` печатает только код.

**Почему `|| echo "000"**: При connection refused curl возвращает exit code 7 (не 0). Без `||` весь shell-скрипт завершился бы с ошибкой (из-за `set -e` в bash). `|| echo "000"` перехватывает ошибку и подставляет значение "000", которое явно не равно "200".

### Stage: Functional Tests

```python
url = base_url.rstrip('/') + test['path'] if 'path' in test else test.get('url', base_url)
```

**Почему `path` вместо `url` в тест-файлах**: Изначально test-файлы содержали `"url": "http://localhost:8000/..."`. При изменении `BASE_URL` на `http://api:8000` тест-файлы тоже пришлось бы менять. С полем `path` (`/health`, `/predict`) хост берётся из `BASE_URL` — конфигурация в одном месте.

**Почему тест через inline Python, а не pytest**: Функциональные тесты проверяют реальный HTTP-сервис без Python-зависимостей. `urllib.request` — стандартная библиотека, не требует pip install. Это делает CD-пайплайн независимым от виртуального окружения.

### Post блок — почему только `failure`, не `always`

```groovy
post {
    success { echo "CD passed — all functional tests green. API is live." }
    failure {
        sh 'docker compose logs api || true'
        sh 'docker compose stop api && docker compose rm -f api || true'
    }
}
```

**Критическая ошибка прошлой версии**: `post { always { docker compose down } }` останавливал **все** сервисы, включая Jenkins. После успешного CD Jenkins убивал сам себя, и пайплайн не мог завершиться корректно.

**Текущее решение**: 
- При успехе: API остаётся живым — это и есть цель CD
- При failure: собираем логи и убираем сломанный контейнер api, Jenkins не трогаем
- `|| true` после команд в failure: даже если `docker compose stop` не сработает — пайплайн завершается с исходным failure-кодом, не маскирует ошибку

---

## 10. Решённые проблемы и их причины

### 10.1 DVC: output не создаётся

**Симптом**: `dvc repro` падает с `output was not created`.
**Причина**: `dvc.yaml` объявлял `data/breast_cancer_orig.csv` как output stage `preprocess`, но `preprocess.py` не создаёт этот файл.
**Fix**: убрать несуществующий output из `dvc.yaml`.
**Урок**: DVC строго проверяет: каждый объявленный output должен быть создан командой.

### 10.2 DVC evaluate: IndentationError

**Симптом**: `IndentationError: unexpected indent` в Python при выполнении evaluate-стадии.
**Причина**: YAML folded-scalar (`>`) после переноса строки добавлял пробел в начало кода Python:
```yaml
cmd: >
  python -c "
import yaml  # ← этой строке предшествует пробел из YAML
```
**Fix**: однострочная команда с `;` без YAML-операторов переноса.
**Урок**: Встроенный Python-код в YAML критически чувствителен к форматированию.

### 10.3 DVC/Git конфликт: дата-файлы в обоих системах

**Симптом**: `dvc repro` выдаёт предупреждение о конфликте, файлы CSV в git и в DVC одновременно.
**Fix**: `git rm --cached data/*.csv` + добавить `data/*.csv` в `.gitignore`.
**Урок**: файл не может одновременно управляться git и быть output DVC-стадии.

### 10.4 Jenkins: permission denied на docker socket

**Симптом**: `Got permission denied while trying to connect to the Docker daemon socket`.
**Причина**: GID docker-группы внутри контейнера Jenkins (999) не совпадает с GID сокета на хосте (0 на Docker Desktop).
**Fix**: runtime entrypoint, который читает фактический GID сокета и подстраивает docker-группу.
**Урок**: GID docker-группы зависит от хоста и не может быть захардкожен в образе.

### 10.5 CRLF ломает bash entrypoint

**Симптом**: контейнер Jenkins в restart loop, `exec format error` или `bad interpreter`.
**Причина**: Windows git конвертирует `LF → CRLF`. Bash-скрипт с `\r\n` внутри Linux-контейнера не запускается — shebang `#!/bin/bash\r` не распознаётся.
**Fix**: `.gitattributes` + `sed -i 's/\r$//'` в Dockerfile.
**Урок**: всегда добавляйте `.gitattributes` при разработке на Windows для проекта, работающего в Linux.

### 10.6 Push Image stage всегда пропускается

**Симптом**: `Stage "Push Image" skipped due to when condition`.
**Причина**: `when { branch 'develop' }` работает только в Multibranch Pipeline. В regular pipeline `BRANCH_NAME` не установлен.
**Fix**: `expression { env.GIT_BRANCH ==~ /.*\/develop/ }` проверяет `GIT_BRANCH = "origin/develop"`.

### 10.7 CD: конфликт имени контейнера

**Симптом**: `Conflict. The container name "/bc-api" is already in use by container "..."`.
**Причина**: контейнер `bc-api` был создан compose-проектом с именем `dev` (имя директории). При запуске CD compose-проект назывался `bc` — другой проект, другой контейнер, но то же имя.
**Fix**: `name: bc` в `docker-compose.yml` — проект всегда называется `bc`, в любом контексте.

### 10.8 CD: `docker compose down` убивает Jenkins

**Симптом**: после успешного CD все контейнеры остановлены, Jenkins не отвечает.
**Причина**: `post { always { docker compose down } }` останавливает все сервисы в compose-файле, включая `bc-jenkins`.
**Fix**: убрать `always`, оставить cleanup только в `failure` и только для `api`.

### 10.9 CD: `localhost:8000` недоступен из Jenkins-контейнера

**Симптом**: `STATUS=000000` при health check, API при этом работает (видно в `docker compose logs`).
**Причина**: `localhost` внутри контейнера `bc-jenkins` — это сам контейнер Jenkins, а не `bc-api`. `curl http://localhost:8000` обращается к несуществующему сервису.
**Fix**: `BASE_URL = "http://api:8000"` — сервис `api` доступен по имени через Docker-сеть `app-network`.
**Урок**: при запуске в контейнере никогда не используйте `localhost` для обращения к другим сервисам. Используйте имена сервисов из docker-compose.

---

## 11. Инварианты — почему не другие решения

### Почему не Multibranch Pipeline

Multibranch Pipeline автоматически создаёт job для каждой ветки. Удобно для больших команд. Минусы: JCasC не поддерживает Multibranch jobs напрямую (требует дополнительного плагина `basic-branch-build-strategies`), усложняет конфигурацию. Regular pipeline + ручное указание ветки в casc.yaml проще и прозрачнее.

### Почему не GitHub Actions вместо Jenkins

GitHub Actions — managed CI/CD, не требует собственной инфраструктуры. Но задача лабораторной работы — изучить самостоятельно поднятый CI/CD на Jenkins. Jenkins демонстрирует: как настраивать runners, как работает JCasC, как управлять credentials. GitHub Actions скрывает эти детали.

### Почему не docker buildx для multi-platform сборки

`docker buildx build --platform linux/amd64,linux/arm64` нужен для публикации образов под несколько архитектур. Учебная среда — единственная архитектура (Windows x86_64). buildx усложняет Dockerfile без практической пользы.

### Почему не Kubernetes вместо docker compose

Kubernetes — оркестратор для production-масштаба: автоскейлинг, rolling updates, self-healing. Docker Compose достаточен для одного хоста с несколькими контейнерами. Добавление K8s без необходимости — overengineering.

### Почему не remote DVC storage (S3/GCS)

Remote storage требует cloud-аккаунт и credentials. В учебной среде это лишняя зависимость. `--no-commit` позволяет использовать DVC для воспроизводимости пайплайна без remote storage.

### Почему `pytest`, а не `unittest`

`pytest` автоматически обнаруживает тесты, имеет богатую систему fixtures, лучший вывод ошибок, plugin-экосистему. `unittest` — более многословный, требует наследования от `TestCase`. `pytest` — де-факто стандарт Python-тестирования.

### Почему `httpx` для тестов API, а не `requests`

`httpx` поддерживает async и sync клиент, интегрируется с FastAPI `TestClient` через `httpx.AsyncClient`. `requests` не поддерживает async. Для тестирования FastAPI `httpx` — рекомендованный выбор.

---

## 12. Воспроизведение с нуля

### Предусловия

- Docker Desktop установлен и запущен
- Git установлен с настройкой `core.autocrlf = false` (или `.gitattributes` в репозитории)
- DockerHub аккаунт с именем пользователя
- GitHub репозиторий с ветками `main` и `develop`

### Шаг 1: Клонировать репозиторий

```bash
git clone https://github.com/YOUR_ORG/YOUR_REPO.git
cd YOUR_REPO
```

### Шаг 2: Создать .env

```bash
cp .env.example .env
# Заполнить:
# DOCKERHUB_USER=your_username
# DOCKERHUB_PASS=your_password
# JENKINS_ADMIN_PASSWORD=admin
```

`.env` должен быть в `.gitignore` — никогда не коммитить.

### Шаг 3: Запустить инфраструктуру

```bash
DOCKERHUB_USER=your_username docker compose up -d --build
```

Первый запуск: сборка образов Jenkins и API ~5-10 минут.

### Шаг 4: Дождаться готовности Jenkins

```bash
# Ждём, пока Jenkins поднимется
docker compose logs -f jenkins
# Ищем строку: "Jenkins is fully up and running"
```

Jenkins UI: http://localhost:8080  
Логин: `admin` / `admin` (или значение `JENKINS_ADMIN_PASSWORD` из `.env`)

### Шаг 5: Проверить автоматическое создание jobs

В Jenkins UI должны появиться:
- `breast-cancer-ci` — CI пайплайн
- `breast-cancer-cd` — CD пайплайн

Если нет — проверить `Manage Jenkins → Configuration as Code → Reload`.

### Шаг 6: Проверить credentials

`Manage Jenkins → Credentials` → должен быть `dockerhub-credentials` с реальными данными.

### Шаг 7: Запустить CI вручную

`breast-cancer-ci → Build Now`

Стадии должны пройти зелёным:
```
Checkout → Setup → Lint → DVC repro → Test → Build Image → Push Image → Security Audit
```

После успеха: образ появится в DockerHub как `:latest` и `:BUILD_NUMBER`.

### Шаг 8: Запустить CD вручную

`breast-cancer-cd → Build Now`

Стадии:
```
Checkout → Pull Image → Compose Up → Functional Tests
```

После успеха: API доступен на http://localhost:8000

### Шаг 9: Проверить API

```bash
curl http://localhost:8000/health
# {"status":"ok","model_loaded":true}

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features":[17.99,10.38,122.8,1001.0,0.1184,0.2776,0.3001,0.1471,0.2419,0.07871,1.095,0.9053,8.589,153.4,0.006399,0.04904,0.05373,0.01587,0.03003,0.006193,25.38,17.33,184.6,2019.0,0.1622,0.6656,0.7119,0.2654,0.4601,0.1189]}'
# {"prediction":0,"probability":0.04,"label":"malignant"}
```

### Шаг 10: Настройка автоматического триггера CI

CI уже настроен на SCM polling `H/5 * * * *`. После любого push в `develop`:
- Jenkins обнаружит изменение в течение 5 минут
- Автоматически запустит CI

### Диагностика частых проблем

| Симптом | Причина | Команда для диагностики |
|---------|---------|------------------------|
| Jenkins не стартует | Ошибка в casc.yaml | `docker compose logs jenkins` |
| `permission denied` на docker | GID mismatch | `docker compose logs jenkins \| grep GID` |
| CI: Push Image skipped | Неверное условие when | Проверить `env.GIT_BRANCH` в логах |
| CD: status=000000 | `localhost` вместо `api` | `BASE_URL` в Jenkinsfile.cd |
| CD: container conflict | Разные compose-проекты | Проверить `name:` в docker-compose.yml |
| DVC repro падает | Несуществующий output | Сравнить outputs в dvc.yaml с реальными файлами |

---

*Конфигурация актуальна для версии 1.0 (ЛР1). В ЛР2 добавляется PostgreSQL, в ЛР3 — Vault, в ЛР4 — Kafka.*
