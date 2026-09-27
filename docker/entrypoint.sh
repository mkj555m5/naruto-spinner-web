#!/bin/sh
# Container entrypoint: boot WARP (optional) then uvicorn
set -u

echo "[entrypoint] USE_WARP=${USE_WARP:-1} PROXY_URL=${PROXY_URL:-<unset>}"

# bring up Cloudflare WARP SOCKS5 proxy in background (non-blocking)
sh /app/docker/warp_setup.sh > /tmp/warp_setup.log 2>&1 &
echo "[entrypoint] warp_setup launched (log: /tmp/warp_setup.log)"

# start the web app (reads $PORT)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
