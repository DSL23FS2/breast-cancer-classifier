FROM jenkins/jenkins:lts

USER root

# ── Системные зависимости ─────────────────────────────────────
# Используем python3 / python3-venv без привязки к версии:
# jenkins:lts базируется на Debian Trixie, где python3 = 3.12
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    curl \
    git \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# ── Symlink python → python3 ──────────────────────────────────
RUN ln -sf /usr/bin/python3 /usr/local/bin/python

# ── DVC ───────────────────────────────────────────────────────
RUN pip install --no-cache-dir --break-system-packages dvc

# ── Docker CLI ────────────────────────────────────────────────
RUN curl -fsSL https://get.docker.com | sh

# ── Плагины Jenkins ───────────────────────────────────────────
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

# ── JCasC конфиг ─────────────────────────────────────────────
COPY casc.yaml /var/jenkins_home/casc.yaml
RUN chown jenkins:jenkins /var/jenkins_home/casc.yaml

# ── Entrypoint: фиксирует GID docker-сокета, затем запускает Jenkins ─────────
# USER остаётся root — скрипт сам делает gosu jenkins перед стартом сервера.
COPY docker-entrypoint.sh /docker-entrypoint.sh
# Убираем Windows CRLF (\r\n) → LF, иначе bash не распознает shebang
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
ENV CASC_JENKINS_CONFIG="/var/jenkins_home/casc.yaml"

ENTRYPOINT ["/docker-entrypoint.sh"]
