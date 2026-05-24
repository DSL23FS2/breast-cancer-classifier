.PHONY: train test up down lint dvc-repro zip help

help:
	@echo "Usage: make <target>"
	@echo "  train      - Train the model"
	@echo "  test       - Run pytest tests"
	@echo "  up         - docker compose up -d"
	@echo "  down       - docker compose down -v"
	@echo "  lint       - Run flake8 linter"
	@echo "  dvc-repro  - Reproduce DVC pipeline"
	@echo "  zip        - Create distribution archive"

train:
	python src/train.py

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

up:
	docker compose up -d

down:
	docker compose down -v

lint:
	flake8 src/ tests/ --max-line-length=100

dvc-repro:
	dvc repro

zip:
	@echo "Creating distribution archive..."
	@powershell -Command "Compress-Archive -Path src,tests,notebooks,config.ini,Dockerfile,docker-compose.yml,requirements.txt,Jenkinsfile,Jenkinsfile.cd,README.md,Makefile -DestinationPath dist.zip -Force"
	@echo "Created dist.zip"
