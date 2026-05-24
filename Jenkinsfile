// Jenkinsfile — CI Pipeline
// Breast Cancer Classifier v1.0
// Stages: Checkout → Lint → Test → DVC repro → Build → Push → dev_sec_ops

pipeline {
    agent any

    environment {
        DOCKERHUB_USER  = credentials('dockerhub-credentials').username
        IMAGE_NAME      = "${DOCKERHUB_USER}/breast-cancer-api"
        IMAGE_TAG       = "${env.BUILD_NUMBER}"
        PYTHONPATH      = "/workspace"
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {

        // ── 1. Checkout ───────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log --oneline -5'
            }
        }

        // ── 2. Setup Python environment ───────────────────────
        stage('Setup') {
            steps {
                sh '''
                    python -m venv .venv
                    .venv/bin/pip install --upgrade pip
                    .venv/bin/pip install -r requirements.txt
                    .venv/bin/pip install flake8 pytest httpx
                '''
            }
        }

        // ── 3. Lint ───────────────────────────────────────────
        stage('Lint') {
            steps {
                sh '.venv/bin/flake8 src/ tests/ --max-line-length=120 --ignore=E501,W503'
            }
        }

        // ── 4. Unit + Integration Tests ───────────────────────
        stage('Test') {
            steps {
                sh '''
                    .venv/bin/pytest tests/test_predict.py tests/test_api.py \
                        -v --tb=short \
                        --junitxml=test-results.xml
                '''
            }
            post {
                always {
                    junit 'test-results.xml'
                }
            }
        }

        // ── 5. DVC repro (ML pipeline) ────────────────────────
        stage('DVC repro') {
            steps {
                sh '''
                    .venv/bin/dvc repro --no-commit
                '''
            }
        }

        // ── 6. Build Docker Image ─────────────────────────────
        stage('Build Image') {
            steps {
                script {
                    withCredentials([usernamePassword(
                        credentialsId: 'dockerhub-credentials',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh """
                            docker build \
                                --build-arg IMAGE_TAG=${IMAGE_TAG} \
                                -t ${DOCKER_USER}/breast-cancer-api:${IMAGE_TAG} \
                                -t ${DOCKER_USER}/breast-cancer-api:latest \
                                .
                        """
                    }
                }
            }
        }

        // ── 7. Push to DockerHub ──────────────────────────────
        stage('Push Image') {
            when {
                anyOf {
                    branch 'develop'
                    branch 'main'
                    branch 'release/*'
                }
            }
            steps {
                script {
                    withCredentials([usernamePassword(
                        credentialsId: 'dockerhub-credentials',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh """
                            echo "${DOCKER_PASS}" | docker login -u "${DOCKER_USER}" --password-stdin
                            docker push ${DOCKER_USER}/breast-cancer-api:${IMAGE_TAG}
                            docker push ${DOCKER_USER}/breast-cancer-api:latest
                            docker logout
                        """
                    }
                }
            }
        }

        // ── 8. Generate dev_sec_ops.yml ───────────────────────
        stage('Security Audit') {
            steps {
                sh '''
                    echo "# dev_sec_ops.yml — last 5 commits SHA" > dev_sec_ops.yml
                    echo "generated_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> dev_sec_ops.yml
                    echo "build: ${BUILD_NUMBER}" >> dev_sec_ops.yml
                    echo "commits:" >> dev_sec_ops.yml
                    git log --pretty=format:"  - sha: %H%n    message: \"%s\"%n    author: %an%n    date: %ai" -5 >> dev_sec_ops.yml
                    cat dev_sec_ops.yml
                '''
                archiveArtifacts artifacts: 'dev_sec_ops.yml', fingerprint: true
            }
        }
    }

    post {
        success {
            echo "CI passed — image breast-cancer-api:${IMAGE_TAG} built and pushed."
        }
        failure {
            echo "CI failed — check logs above."
        }
        always {
            cleanWs()
        }
    }
}
