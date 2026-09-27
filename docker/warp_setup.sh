#!/bin/sh
# ─────────────────────────────────────────────────────────────
# WARP setup: register a Cloudflare WARP account via wgcf,
# then run wireproxy (userspace WireGuard) as a local SOCKS5 proxy.
# Works in containers WITHOUT TUN/NET_ADMIN privileges.
# Result: socks5://127.0.0.1:25344 → Cloudflare WARP network
#
# Verified command syntax (wgcf v2.3.0 / wireproxy windtf v1.1.3):
#   wgcf register  --accept-tos --config <account.toml>
#   wgcf generate  --config <account.toml> -p <profile.conf>
#   wireproxy -n -c <conf>   (configtest)   |  wireproxy -c <conf>
# ─────────────────────────────────────────────────────────────
WGCF=/usr/local/bin/wgcf
WIREPROXY=/usr/local/bin/wireproxy
SOCKS_PORT="${WARP_SOCKS_PORT:-25344}"

# persist profile if a Railway volume is mounted at /data, else /tmp
DATA_DIR="/data"
if [ ! -d "$DATA_DIR" ] || [ ! -w "$DATA_DIR" ]; then
  DATA_DIR="/tmp"
fi
ACCOUNT="$DATA_DIR/wgcf-account.toml"
PROFILE="$DATA_DIR/wgcf-profile.conf"
WIREPROXY_CONF="$DATA_DIR/wireproxy.conf"

log() { echo "[warp-setup] $*"; }

# build wireproxy conf from wgcf profile (drop ListenPort, add SOCKS5 listener)
make_conf() {
  {
    grep -v -E '^\s*ListenPort' "$PROFILE"
    echo ""
    echo "[Socks5]"
    echo "BindAddress = 127.0.0.1:${SOCKS_PORT}"
  } > "$WIREPROXY_CONF"
}

# fresh WARP account + profile
register_and_generate() {
  rm -f "$ACCOUNT" "$PROFILE" "$WIREPROXY_CONF"
  log "registering new WARP account (wgcf)..."
  if ! "$WGCF" register --accept-tos --config "$ACCOUNT" 2>&1; then
    log "ERROR: wgcf register failed (no access to CF API?)"
    return 1
  fi
  if ! "$WGCF" generate --config "$ACCOUNT" -p "$PROFILE" 2>&1; then
    log "ERROR: wgcf generate failed"
    return 1
  fi
  return 0
}

# 1) skip entirely?
if [ "${USE_WARP:-1}" = "0" ]; then
  log "USE_WARP=0 → skipping WARP setup (direct mode)"
  exit 0
fi

# 2) generate profile if missing
if [ ! -f "$PROFILE" ]; then
  register_and_generate || exit 1
fi
log "profile ready: $PROFILE"

# 3) build wireproxy config
make_conf

# 4) validate config; if stale/corrupt → one fresh registration
if ! "$WIREPROXY" -n -c "$WIREPROXY_CONF" > /dev/null 2>&1; then
  log "WARN: existing profile invalid — re-registering fresh account..."
  if register_and_generate; then
    make_conf
  else
    log "ERROR: re-registration failed — app will run DIRECT"
    exit 1
  fi
fi
log "wireproxy config validated OK"

# 5) launch wireproxy
log "starting wireproxy (socks5://127.0.0.1:${SOCKS_PORT})..."
"$WIREPROXY" -c "$WIREPROXY_CONF" > /tmp/wireproxy.log 2>&1 &

# 6) wait until healthy (max ~90s; wireproxy keeps retrying in background —
#    /api/proxy does a live check so a late tunnel is still detected)
i=0
while [ $i -lt 15 ]; do
  TRACE=$(curl -s --max-time 6 --socks5-hostname "127.0.0.1:${SOCKS_PORT}" https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null)
  if echo "$TRACE" | grep -q "warp=on"; then
    log "✓ WARP is UP ($(echo "$TRACE" | grep '^ip=' | head -1))"
    echo "$TRACE" | grep -E '^(ip|loc|colo|warp)=' > /tmp/warp_status.txt
    exit 0
  fi
  i=$((i+1))
  sleep 2
done

log "WARN: wireproxy running but WARP handshake failed — app falls back to DIRECT"
log "      (UDP 2408 outbound may be blocked; check /tmp/wireproxy.log or set USE_WARP=0)"
tail -n 5 /tmp/wireproxy.log 2>/dev/null
exit 0
