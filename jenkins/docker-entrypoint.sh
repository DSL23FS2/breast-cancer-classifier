#!/bin/bash
set -e

# ── Fix docker socket GID at runtime ─────────────────────────────────────────
# The GID of /var/run/docker.sock on the host may differ from the docker group
# GID baked into the image. We read the actual GID at container start and
# patch the group so jenkins can reach the socket.
if [ -S /var/run/docker.sock ]; then
    SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    CUR_GID=$(getent group docker | cut -d: -f3)
    if [ "$SOCK_GID" != "$CUR_GID" ]; then
        groupmod -g "$SOCK_GID" docker
    fi
    usermod -aG docker jenkins
fi

# ── Drop to jenkins user and start Jenkins ────────────────────────────────────
exec gosu jenkins /bin/tini -- /usr/local/bin/jenkins.sh "$@"
