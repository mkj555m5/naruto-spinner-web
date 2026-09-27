# -*- coding: utf-8 -*-
"""
NARUTO SPINNER CORE — ported 1:1 from all.py (OB55 EDITION, MULTI-EVENT)
Credit: KAWSAR | x64 — Telegram: @kawsar449x

All crypto / protobuf / networking logic preserved exactly as the original.
"""
import os
import re
import time
import json
import gzip as _gzip
from datetime import datetime

import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ─────────────────────────────────────────────
#  CONSTANTS (identical to original)
# ─────────────────────────────────────────────
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

LOGIN_HOST   = "clientbp.ppmainecoonghj.com"
DEFAULT_URL  = f"https://{LOGIN_HOST}"
RELEASE_VER  = "OB55"
UNITY_VER    = "2018.4.12f1"

EXTERNAL_API_URL = "https://ff-jwt-gen-api.lovable.app//api/public/token"

# ── PROXY / WARP CONFIG ──────────────────────────────────────
WARP_SOCKS = os.environ.get("WARP_SOCKS", "socks5://127.0.0.1:25344")


def get_proxy_url() -> str:
    """Resolve outbound proxy: PROXY_URL env wins, else WARP if enabled (default on)."""
    p = (os.environ.get("PROXY_URL") or "").strip()
    if p:
        return p
    if os.environ.get("USE_WARP", "1").strip().lower() not in ("0", "false", "no", "off"):
        return WARP_SOCKS
    return ""


def status_err(status: int) -> str:
    """Human-friendly error for HTTP status codes."""
    if status == 999:
        return "Connection Fail"
    if status == 400:
        return "HTTP 400 (السيرفر رفض الطلب — غالباً IP محجوب، فعّل WARP أو غيّر البروكسي)"
    if status in (401, 403):
        return f"HTTP {status} (توكن غير صالح أو محظور)"
    if status == 429:
        return "HTTP 429 (Rate Limit — قلل التزامن)"
    return f"HTTP {status}"

# ── EVENT DEFINITIONS ────────────────────────────────────────
EVENTS = {
    "naruto": {
        "name":     "NARUTO",
        "payload":  {1: 33, 2: 1, 3: 553, 4: 5, 13: 2},
        "prefix":   "NARUTO",
        "emoji":    "🍥",
    },
    "skywin": {
        "name":     "NARUTO SKYWIN",
        "payload":  {1: 11, 2: 1, 3: 553, 4: 5, 13: 2},
        "prefix":   "SKYWIN",
        "emoji":    "☁️",
    },
    "fist": {
        "name":     "NARUTO FIST",
        "payload":  {1: 29, 2: 1, 3: 553, 4: 3, 13: 2},
        "prefix":   "FIST",
        "emoji":    "👊",
    },
    "sasuke": {
        "name":     "SASUKE BUNDLE",
        "payload":  {1: 91, 2: 1, 3: 554, 4: 5, 13: 2},
        "prefix":   "SASUKE",
        "emoji":    "⚡",
    },
}

# ── ITEM DATABASE (merged across all events) ──
ITEM_DB = {
    # ── NARUTO (event 1) ──
    710047022: ("NARUTO BUNDLE",         "VERY_RARE"),
    909047015: ("RASENGAN EMOTE",        "RARE"),
    907104746: ("HOKAGE ROCK GLOW WALL", "RARE"),
    904047008: ("HOKAGE GLOW WALL",      "NORMAL"),
    903047008: ("RASENGAN SKIN",         "NORMAL"),

    # ── NARUTO SKYWIN (event 2) ──
    911004701: ("NARUTO SKYWIN",         "VERY_RARE"),
    907104744: ("M4A1 - NARUTO THEME",   "RARE"),
    211047048: ("OBITO MASK",            "RARE"),

    # ── NARUTO FIST (event 3) ──
    907104745: ("FIST",                  "VERY_RARE"),

    # ── SASUKE BUNDLE (event 4) ──
    710047023: ("SASUKE BUNDLE",         "VERY_RARE"),
    907104743: ("KATANA",                "RARE"),
    907104742: ("KATANA",                "RARE"),
    907104748: ("GROZA",                 "RARE"),
}


def classify_item(item_id: int):
    if item_id in ITEM_DB:
        return ITEM_DB[item_id]
    return (f"UNKNOWN_{item_id}", "NORMAL")


# ─────────────────────────────────────────────
#  ACCOUNT FILE LOADER (identical to original)
# ─────────────────────────────────────────────
def load_accounts_text(raw: str):
    """Accepts JSON array / JSON with accounts key / kawsar block text."""
    # ── try JSON first ──
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and 'accounts' in data:
            records = data['accounts']
        else:
            records = None

        if records is not None:
            normalized = []
            for r in records:
                if not isinstance(r, dict):
                    continue
                entry = dict(r)

                if 'uid' not in entry or not entry['uid']:
                    for alt in ('Account_uid', 'external_uid', 'Open_id'):
                        if r.get(alt):
                            entry['uid'] = str(r[alt])
                            break

                if 'password' not in entry or not entry['password']:
                    for alt in ('Password', 'PASSWORD', 'pass', 'Pass'):
                        if r.get(alt):
                            entry['password'] = r[alt]
                            break

                if 'access_token' not in entry and r.get('Access_token'):
                    entry['access_token'] = r['Access_token']
                if 'jwt' not in entry and r.get('Jwt_token'):
                    entry['jwt'] = r['Jwt_token']
                if 'region' not in entry and r.get('Region'):
                    entry['region'] = r['Region']

                normalized.append(entry)
            return normalized
    except Exception:
        pass

    # ── fall back to block-text parser ──
    accounts = []
    current = {}
    raw = re.sub(r'\033\[[0-9;]*m', '', raw)

    FIELD_MAP = {
        "UID":          "uid",
        "GAME UID":     "game_uid",
        "NICKNAME":     "nickname",
        "PASSWORD":     "password",
        "REGION":       "region",
        "ACCESS TOKEN": "access_token",
        "OPEN ID":      "open_id",
        "JWT":          "jwt",
        "ONLINE IP":    "online_ip_port",
        "ACCOUNT IP":   "account_ip_port",
    }

    for line in raw.splitlines():
        line = line.strip()

        if not line or set(line) <= set('─-—_ '):
            if current.get("uid"):
                accounts.append(current)
                current = {}
            continue

        m = re.match(r'^([A-Z][A-Z0-9 _]+?)\s*:\s*(.*)$', line)
        if not m:
            continue

        label = m.group(1).strip()
        value = m.group(2).strip()

        key = FIELD_MAP.get(label)
        if key:
            current[key] = value

    if current.get("uid"):
        accounts.append(current)

    if not accounts:
        raise ValueError("No accounts found — file is neither JSON nor kawsar block format")

    return accounts


# ── AES (identical) ──
def encrypt_data(data: bytes) -> bytes:
    c = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return c.encrypt(pad(data, AES.block_size))


# ── PROTOBUF helpers (identical) ──
def _varint(n):
    out = []
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)


def _field(fn, v):
    if isinstance(v, bool):  return _varint((fn << 3) | 0) + _varint(int(v))
    if isinstance(v, int):   return _varint((fn << 3) | 0) + _varint(v)
    if isinstance(v, bytes): return _varint((fn << 3) | 2) + _varint(len(v)) + v
    if isinstance(v, str):
        b = v.encode()
        return _varint((fn << 3) | 2) + _varint(len(b)) + b
    raise TypeError(f"unsupported {type(v)}")


def assemble_proto(fields: dict) -> bytes:
    return b''.join(_field(int(k), v) for k, v in fields.items())


def _read_varint(data, pos):
    result = 0; shift = 0
    while pos < len(data):
        bv = data[pos]; pos += 1
        result |= (bv & 0x7F) << shift
        if not (bv & 0x80): break
        shift += 7
    return result, pos


def _try_parse_proto(raw: bytes):
    if not raw: return None
    out = {}; pos = 0; seen = 0
    try:
        while pos < len(raw):
            tag, pos = _read_varint(raw, pos)
            if tag == 0: return None
            fn, wt = tag >> 3, tag & 7
            if fn == 0 or fn > 536870911: return None
            if wt == 0:
                v, pos = _read_varint(raw, pos)
                out[fn] = v
            elif wt == 2:
                ln, pos = _read_varint(raw, pos)
                if pos + ln > len(raw): return None
                val = raw[pos:pos + ln]; pos += ln
                n = _try_parse_proto(val)
                if n and len(n) >= 1:
                    out[fn] = n
                else:
                    try:    out[fn] = val.decode('utf-8')
                    except: out[fn] = val.hex()
            elif wt == 5:
                if pos + 4 > len(raw): return None
                out[fn] = raw[pos:pos + 4].hex(); pos += 4
            elif wt == 1:
                if pos + 8 > len(raw): return None
                out[fn] = raw[pos:pos + 8].hex(); pos += 8
            else: return None
            seen += 1
        return out if seen else None
    except: return None


# ── BODY BUILDERS ──
def build_payload(event_key: str) -> bytes:
    """Build encrypted payload for a given event."""
    fields = EVENTS[event_key]["payload"]
    return encrypt_data(assemble_proto(fields))


# ── RESPONSE PARSER (identical) ──
def parse_gacha_response(data: bytes) -> dict:
    if data and data[:2] == b'\x1f\x8b':
        try: data = _gzip.decompress(data)
        except: pass

    parsed = _try_parse_proto(data) or {}
    items = []

    inner = parsed.get(1)
    if isinstance(inner, dict):
        raw = inner.get(2, "")
        if isinstance(raw, str):
            m = re.match(r'\s*(\d+)\s*[→\-–>]+\s*(.+?)\s*$', raw)
            if m:
                iid = int(m.group(1))
                iname = m.group(2).strip()
                items.append({"id": iid, "name": iname})

    if not items:
        for mm in re.finditer(r'\b(\d{9})\b', str(parsed)):
            iid = int(mm.group(1))
            if not any(it['id'] == iid for it in items):
                items.append({"id": iid, "name": None})

    for it in items:
        default_name, rarity = classify_item(it['id'])
        if not it['name'] or it['name'].startswith("UNKNOWN"):
            it['name'] = default_name
        it['rarity'] = rarity

    return {"items": items, "raw": parsed}


# ── EXTERNAL JWT API (identical) ──
async def get_token(session: aiohttp.ClientSession, uid, password, retries):
    for attempt in range(retries):
        try:
            params = {'uid': uid, 'password': password}
            async with session.get(EXTERNAL_API_URL, params=params,
                                   ssl=False,
                                   timeout=aiohttp.ClientTimeout(total=15)) as res:
                if res.status == 200:
                    data = await res.json()
                    if data.get("success"):
                        token = data.get("token")
                        if token and isinstance(token, str) and len(token) > 50:
                            return token
        except Exception:
            await asyncio_sleep()
    return None


async def asyncio_sleep():
    import asyncio
    await asyncio.sleep(0.4)


# ── GACHA REQUEST (identical) ──
async def gacha_req(session: aiohttp.ClientSession, token, payload, url, max_retries):
    if not url.endswith("/PurchaseGacha"):
        url = f"{url}/PurchaseGacha"

    headers = {
        'User-Agent':      f"UnityPlayer/{UNITY_VER} (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        'Accept':          "*/*",
        'Accept-Encoding': "deflate, gzip",
        'Authorization':   f"Bearer {token}",
        'X-GA':            "v1 1",
        'X-Ga-Sv':         str(int(time.time())),
        'ReleaseVersion':  RELEASE_VER,
        'Content-Type':    "application/x-www-form-urlencoded",
        'X-Unity-Version': UNITY_VER,
        'Host':            LOGIN_HOST,
    }

    last_status = 0
    for _ in range(1, max_retries + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with session.post(url, headers=headers, data=payload,
                                    ssl=False, timeout=timeout) as res:
                last_status = res.status
                if res.status == 200:
                    body = await res.read()
                    return 200, body
                elif res.status in (401, 403):
                    return res.status, None
                else:
                    import asyncio
                    await asyncio.sleep(0.2)
        except Exception:
            last_status = 999
            import asyncio
            await asyncio.sleep(0.3)
    return last_status, None
