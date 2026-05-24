FROM jenkins/jenkins:lts

USER root

# ── Системные зависимости ─────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Symlink python → python3.11 ───────────────────────────────
RUN ln -sf /usr/bin/python3.11 /usr/local/bin/python \
 && ln -sf /usr/bin/python3.11 /usr/local/bin/python3

# ── DVC ───────────────────────────────────────────────────────
RUN pip install --no-cache-dir --break-system-packages dvc

# ── Docker CLI ────────────────────────────────────────────────
RUN curl -fsSL https://get.docker.com | sh

# ── Плагины Jenkins (файл plugins.txt обрабатывается jenkins-plugin-cli) ──
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

# ── JCasC конфиг ─────────────────────────────────────────────
COPY casc.yaml /var/jenkins_home/casc.yaml
RUN chown jenkins:jenkins /var/jenkins_home/casc.yaml

USER jenkins

ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
ENV CASC_JENKINS_CONFIG="/var/jenkins_home/casc.yaml"
