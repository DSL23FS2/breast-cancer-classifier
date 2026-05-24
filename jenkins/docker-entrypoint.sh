#!/bin/bash
set -e

# ── Fix docker socket permissions at runtime ──────────────────────────────────
# On Docker Desktop (Windows/macOS) the socket is owned by root (GID=0).
# groupmod to GID 0 is not possible, so we open the socket to all users.
# On Linux the socket usually has a dedicated docker group — we match GID instead.
if [ -S /var/run/docker.sock ]; then
    SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    if [ "$SOCK_GID" = "0" ]; then
        chmod 666 /var/run/docker.sock
    else
        CUR_GID=$(getent group docker | cut -d: -f3)
        if [ "$SOCK_GID" != "$CUR_GID" ]; then
            groupmod -g "$SOCK_GID" docker
        fi
        usermod -aG docker jenkins
    fi
fi

# ── Drop to jenkins user and start Jenkins ────────────────────────────────────
exec gosu jenkins /bin/tini -- /usr/local/bin/jenkins.sh "$@"
