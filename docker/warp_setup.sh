#!/bin/sh
# ─────────────────────────────────────────────────────────────
# WARP setup: register a Cloudflare WARP account via wgcf,
# then run wireproxy (userspace WireGuard) as a local SOCKS5 proxy.
# Works in containers WITHOUT TUN/NET_ADMIN privileges.
# Result: socks5://127.0.0.1:25344 → Cloudflare WARP network
# ─────────────────────────────────────────────────────────────
WGCF=/usr/local/bin/wgcf
WIREPROXY=/usr/local/bin/wireproxy

# persist profile if a Railway volume is mounted at /data, else /tmp
DATA_DIR="/data"
if [ ! -d "$DATA_DIR" ] || [ ! -w "$DATA_DIR" ]; then
  DATA_DIR="/tmp"
fi
PROFILE="$DATA_DIR/wgcf-profile.conf"
WIREPROXY_CONF="$DATA_DIR/wireproxy.conf"

log() { echo "[warp-setup] $*"; }

# 1) skip entirely?
if [ "${USE_WARP:-1}" = "0" ]; then
  log "USE_WARP=0 → skipping WARP setup (direct mode)"
  exit 0
fi

# 2) generate profile if missing
if [ ! -f "$PROFILE" ]; then
  log "registering new WARP account (wgcf)..."
  if ! "$WGCF" register --accept-tos --config "$DATA_DIR/wgcf-account.toml" 2>&1; then
    log "ERROR: wgcf register failed (no internet to CF API?)"
    exit 1
  fi
  if ! "$WGCF" generate --config "$DATA_DIR/wgcf-account.toml" -p "$PROFILE" 2>&1; then
    log "ERROR: wgcf generate failed"
    exit 1
  fi
fi
log "profile ready: $PROFILE"

# 3) build wireproxy config (append SOCKS5 listener, drop ListenPort)
{
  grep -v -E '^\s*ListenPort' "$PROFILE"
  echo ""
  echo "[Socks5]"
  echo "BindAddress = 127.0.0.1:25344"
} > "$WIREPROXY_CONF"

# 4) launch wireproxy
log "starting wireproxy (socks5://127.0.0.1:25344)..."
"$WIREPROXY" -c "$WIREPROXY_CONF" >/tmp/wireproxy.log 2>&1 &

# 5) wait until healthy (max ~60s)
i=0
while [ $i -lt 30 ]; do
  TRACE=$(curl -s --max-time 6 --socks5-hostname 127.0.0.1:25344 https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null)
  if echo "$TRACE" | grep -q "warp=on"; then
    log "✓ WARP is UP ($(echo "$TRACE" | grep '^ip=' | head -1))"
    exit 0
  fi
  i=$((i+1))
  sleep 2
done

log "WARN: wireproxy started but WARP not healthy yet — check /tmp/wireproxy.log"
exit 0
