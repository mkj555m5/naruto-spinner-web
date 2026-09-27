# -*- coding: utf-8 -*-
"""
NARUTO MULTI-SPINNER — WEB EDITION (Railway Ready)
FastAPI server: API + live state + static dashboard.
Original logic: KAWSAR | x64 (Telegram: @kawsar449x)
"""
import os
import time
import asyncio
import json as _json
from collections import deque
from datetime import datetime

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List

from . import core
from .core import EVENTS, build_payload, load_accounts_text, get_token, gacha_req, parse_gacha_response

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")

MAX_LOGS = 400

# ─────────────────────────────────────────────
#  GLOBAL JOB STATE (single job at a time)
# ─────────────────────────────────────────────
class JobState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.running = False
        self.finished = False
        self.stop_flag = False
        self.event_label = ""
        self.accounts_total = 0
        self.accounts_done = 0
        self.tokens_ready = 0
        self.batch_label = ""
        self.counters = {"very_rare": 0, "rare": 0, "normal": 0, "total_items": 0}
        self.logs = deque(maxlen=MAX_LOGS)
        self.hits = []
        self.items = []
        self.started_at = None
        self.finished_at = None
        self.error = None

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "finished": self.finished,
            "event": self.event_label,
            "accounts_total": self.accounts_total,
            "accounts_done": self.accounts_done,
            "tokens_ready": self.tokens_ready,
            "batch": self.batch_label,
            "counters": self.counters,
            "logs": list(self.logs),
            "hits": list(self.hits)[-100:],
            "items": list(self.items)[-300:],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


STATE = JobState()
JOB_TASK: Optional[asyncio.Task] = None


def log(msg: str, level: str = "info"):
    ts = time.strftime("%H:%M:%S")
    STATE.logs.append({"t": ts, "msg": msg, "level": level})


# ─────────────────────────────────────────────
#  TOKEN PREFETCH (identical flow to original)
# ─────────────────────────────────────────────
jwt_cache: dict = {}
jwt_lock = asyncio.Lock()


async def prefetch_all_tokens(session, accounts: list, retries: int, concurrency: int = 20):
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(acc):
        if STATE.stop_flag:
            return
        uid = str(acc.get("uid", ""))
        pwd = acc.get("password", "")
        if not uid or not pwd:
            return
        token = await get_token(session, uid, pwd, retries)
        async with jwt_lock:
            jwt_cache[uid] = token

    await asyncio.gather(*[_bounded(acc) for acc in accounts], return_exceptions=True)
    warm = sum(1 for v in jwt_cache.values() if v)
    STATE.tokens_ready = warm
    log(f"[✓] Tokens ready: {warm}/{len(accounts)}", "ok")


# ─────────────────────────────────────────────
#  ACCOUNT PROCESSOR — one item hit shared logic
# ─────────────────────────────────────────────
async def handle_items(ev_name: str, uid: str, pwd: str, found_items: list):
    for item in found_items:
        iid, iname, rarity = item['id'], item['name'], item['rarity']
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event": ev_name,
            "guestUid": uid,
            "item_id": iid,
            "item_name": iname,
            "rarity": rarity,
        }
        STATE.items.append(entry)
        STATE.counters["total_items"] += 1

        if rarity == "VERY_RARE":
            STATE.counters["very_rare"] += 1
            hit = f"[{ev_name}] UID: {uid} | Pass: {pwd} | ★★★ VERY RARE: {iname} (ID: {iid})"
            STATE.hits.append(hit)
            log(f"★★★ VERY RARE ★★★ {iname} (ID: {iid})", "vrare")
        elif rarity == "RARE":
            STATE.counters["rare"] += 1
            hit = f"[{ev_name}] UID: {uid} | Pass: {pwd} | ⭐ RARE: {iname} (ID: {iid})"
            STATE.hits.append(hit)
            log(f"⭐ RARE ⭐ {iname} (ID: {iid})", "rare")
        else:
            STATE.counters["normal"] += 1
            log(f"📦 NORMAL {iname} (ID: {iid})", "item")


async def process_account_single_event(sem, session, acc, idx, total, target_url,
                                       event_key, login_retry, spin_retry):
    if STATE.stop_flag:
        return
    async with sem:
        if STATE.stop_flag:
            return
        uid = str(acc.get("uid", "Unknown"))
        pwd = acc.get("password", "Unknown")
        ev = EVENTS[event_key]

        log(f"➤ [{idx+1}/{total}] UID: {uid} | Event: {ev['name']}", "head")

        async with jwt_lock:
            token = jwt_cache.get(uid)
        if not token:
            token = await get_token(session, uid, pwd, login_retry)
        if not token:
            log("   [✗] Token Failed", "err")
            return

        payload = build_payload(event_key)
        status_code, resp = await gacha_req(session, token, payload, target_url, spin_retry)

        if status_code == 200 and resp:
            try:
                parsed = parse_gacha_response(resp)
                found = parsed.get('items', [])
                if not found:
                    log("   ✓ Spin Success — no items in response", "ok")
                    return
                await handle_items(ev['name'], uid, pwd, found)
            except Exception as e:
                log(f"   [!] Parse Error: {e}", "err")
        else:
            err_msg = f"HTTP {status_code}" if status_code != 999 else "Connection Fail"
            log(f"   [✗] {err_msg}", "err")


async def process_account_all_events(sem, session, acc, idx, total, target_url,
                                     login_retry, spin_retry):
    if STATE.stop_flag:
        return
    async with sem:
        if STATE.stop_flag:
            return
        uid = str(acc.get("uid", "Unknown"))
        pwd = acc.get("password", "Unknown")

        log(f"➤ [{idx+1}/{total}] UID: {uid} | ALL EVENTS", "head")

        async with jwt_lock:
            token = jwt_cache.get(uid)
        if not token:
            token = await get_token(session, uid, pwd, login_retry)
        if not token:
            log("   [✗] Token Failed", "err")
            return

        for event_key, ev in EVENTS.items():
            if STATE.stop_flag:
                return
            payload = build_payload(event_key)
            status_code, resp = await gacha_req(session, token, payload, target_url, spin_retry)

            if status_code == 200 and resp:
                try:
                    parsed = parse_gacha_response(resp)
                    found = parsed.get('items', [])
                    if not found:
                        log(f"   ✓ {ev['name']}: no items", "dim")
                    else:
                        await handle_items(ev['name'], uid, pwd, found)
                except Exception as e:
                    log(f"   [!] Parse Error: {e}", "err")
            else:
                err_msg = f"HTTP {status_code}" if status_code != 999 else "Connection Fail"
                log(f"   [✗] {ev['name']}: {err_msg}", "err")

            await asyncio.sleep(0.3)


async def process_account_custom(sem, session, acc, idx, total, target_url,
                                 payload, login_retry, spin_retry):
    if STATE.stop_flag:
        return
    async with sem:
        if STATE.stop_flag:
            return
        uid = str(acc.get("uid", "Unknown"))
        pwd = acc.get("password", "Unknown")

        log(f"➤ [{idx+1}/{total}] UID: {uid} | CUSTOM", "head")

        async with jwt_lock:
            token = jwt_cache.get(uid)
        if not token:
            token = await get_token(session, uid, pwd, login_retry)
        if not token:
            log("   [✗] Token Failed", "err")
            return

        status_code, resp = await gacha_req(session, token, payload, target_url, spin_retry)

        if status_code == 200 and resp:
            try:
                parsed = parse_gacha_response(resp)
                found = parsed.get('items', [])
                if not found:
                    log("   ✓ Spin Success — no items", "ok")
                    return
                await handle_items("CUSTOM", uid, pwd, found)
            except Exception as e:
                log(f"   [!] Parse Error: {e}", "err")
        else:
            err_msg = f"HTTP {status_code}" if status_code != 999 else "Connection Fail"
            log(f"   [✗] {err_msg}", "err")


# ─────────────────────────────────────────────
#  MAIN JOB RUNNER (mirrors all.py main())
# ─────────────────────────────────────────────
async def run_job(accounts: list, cfg: dict):
    try:
        event = cfg["event"]                    # naruto|skywin|fist|sasuke|all|custom
        custom_hex = cfg.get("custom_hex")      # str hex or None
        concurrency = max(1, int(cfg.get("concurrency", 5)))
        batch_size = max(1, int(cfg.get("batch_size", 50)))
        login_retry = max(1, int(cfg.get("login_retry", 3)))
        spin_retry = 3
        start_from = max(0, int(cfg.get("start_from", 1)) - 1)
        if start_from >= len(accounts):
            start_from = 0

        custom_payload = None
        if event == "custom":
            try:
                custom_payload = bytes.fromhex((custom_hex or "").replace(" ", ""))
                log(f"[✓] Custom payload loaded ({len(custom_payload)} bytes)", "ok")
            except Exception as e:
                raise ValueError(f"Invalid hex payload: {e}")

        ev_label = ("ALL EVENTS (1→2→3→4)" if event == "all"
                    else "CUSTOM PAYLOAD" if event == "custom"
                    else EVENTS[event]["name"])
        STATE.event_label = ev_label
        log(f"[✓] MODE: {ev_label}", "ok")
        if event != "custom" and event != "all":
            log(f"    payload → {EVENTS[event]['payload']}", "dim")

        target_url = core.DEFAULT_URL
        log(f"[ SERVER ] BD / Mena → {target_url}", "info")
        log(f"[*] Accounts: {len(accounts)} | Concurrency: {concurrency} | Batch: {batch_size}", "info")

        semaphore = asyncio.Semaphore(concurrency)
        accounts_to_process = accounts[start_from:]
        STATE.accounts_total = len(accounts_to_process)

        batches = [accounts_to_process[i:i + batch_size]
                   for i in range(0, len(accounts_to_process), batch_size)]
        total_batches = len(batches)

        async with aiohttp.ClientSession() as session:
            for batch_idx, batch in enumerate(batches):
                if STATE.stop_flag:
                    log("[!] Stopped by user.", "err")
                    break

                batch_start_abs = start_from + batch_idx * batch_size
                STATE.batch_label = f"{batch_idx + 1}/{total_batches}"
                log(f"[BATCH {batch_idx + 1}/{total_batches}] "
                    f"Accounts {batch_start_abs + 1}–{batch_start_abs + len(batch)} "
                    f"of {len(accounts)}", "head")

                jwt_cache.clear()
                log(f"[»] Prefetching JWT tokens ({len(batch)} accounts)...", "info")
                await prefetch_all_tokens(
                    session, batch,
                    retries=login_retry,
                    concurrency=min(concurrency * 4, 40),
                )

                if STATE.stop_flag:
                    log("[!] Stopped by user.", "err")
                    break

                if event == "all":
                    tasks = [asyncio.create_task(process_account_all_events(
                        semaphore, session, acc, batch_start_abs + i, len(accounts),
                        target_url, login_retry, spin_retry))
                        for i, acc in enumerate(batch)]
                elif event == "custom":
                    tasks = [asyncio.create_task(process_account_custom(
                        semaphore, session, acc, batch_start_abs + i, len(accounts),
                        target_url, custom_payload, login_retry, spin_retry))
                        for i, acc in enumerate(batch)]
                else:
                    tasks = [asyncio.create_task(process_account_single_event(
                        semaphore, session, acc, batch_start_abs + i, len(accounts),
                        target_url, event, login_retry, spin_retry))
                        for i, acc in enumerate(batch)]

                done = 0
                for fut in asyncio.as_completed(tasks):
                    try:
                        await fut
                    except Exception:
                        pass
                    done += 1
                    STATE.accounts_done = (batch_start_abs - start_from) + done

                log(f"[✓] Batch {batch_idx + 1} done — "
                    f"VR:{STATE.counters['very_rare']} R:{STATE.counters['rare']} "
                    f"N:{STATE.counters['normal']}", "ok")

        c = STATE.counters
        log("==========================================", "head")
        log("      NARUTO MULTI-EVENT REPORT", "head")
        log("==========================================", "head")
        log(f" ★★★ VERY RARE: {c['very_rare']}", "vrare" if c['very_rare'] else "dim")
        log(f" ⭐ RARE:        {c['rare']}", "rare" if c['rare'] else "dim")
        log(f" 📦 NORMAL:      {c['normal']}", "item")
        log(f" Total Items:    {c['total_items']}", "ok")
        log(f" Accounts:       {STATE.accounts_total}", "info")
        log("==========================================", "head")

    except asyncio.CancelledError:
        log("[!] Job cancelled.", "err")
    except Exception as e:
        STATE.error = str(e)
        log(f"[!] FATAL: {e}", "err")
    finally:
        STATE.running = False
        STATE.finished = True
        STATE.finished_at = time.strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────
#  FASTAPI APP
# ─────────────────────────────────────────────
app = FastAPI(title="NARUTO MULTI-SPINNER — Web Edition", version="1.0.0")


class StartRequest(BaseModel):
    accounts_text: str = Field(..., description="Accounts JSON or block text")
    event: str = Field("naruto", description="naruto|skywin|fist|sasuke|all|custom")
    custom_hex: Optional[str] = Field(None)
    concurrency: int = Field(5, ge=1, le=50)
    batch_size: int = Field(50, ge=1, le=500)
    login_retry: int = Field(3, ge=1, le=10)
    start_from: int = Field(1, ge=1, le=10_000_000)


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/events")
async def api_events():
    return {
        "events": [
            {"key": k, "name": v["name"], "payload": v["payload"], "emoji": v["emoji"]}
            for k, v in EVENTS.items()
        ],
        "server": core.DEFAULT_URL,
        "item_db": {str(k): {"name": v[0], "rarity": v[1]} for k, v in core.ITEM_DB.items()},
    }


@app.post("/api/parse")
async def api_parse(body: dict):
    raw = (body or {}).get("accounts_text", "")
    if not raw.strip():
        raise HTTPException(400, "Empty accounts text")
    try:
        accounts = load_accounts_text(raw)
    except Exception as e:
        raise HTTPException(400, str(e))
    uids = [str(a.get("uid", "?")) for a in accounts]
    return {"count": len(accounts), "uids_preview": uids[:20]}


@app.post("/api/start")
async def api_start(req: StartRequest):
    global JOB_TASK
    if STATE.running:
        raise HTTPException(409, "A job is already running — stop it first")

    try:
        accounts = load_accounts_text(req.accounts_text)
    except Exception as e:
        raise HTTPException(400, f"Failed to load accounts: {e}")

    if req.event not in list(EVENTS.keys()) + ["all", "custom"]:
        raise HTTPException(400, f"Unknown event: {req.event}")
    if req.event == "custom" and not req.custom_hex:
        raise HTTPException(400, "custom_hex required for custom event")

    STATE.reset()
    jwt_cache.clear()
    STATE.running = True
    STATE.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    STATE.accounts_total = len(accounts)
    log(f"[+] Loaded {len(accounts)} accounts", "ok")
    log("[✓] All requirements ready!", "ok")

    cfg = {
        "event": req.event,
        "custom_hex": req.custom_hex,
        "concurrency": req.concurrency,
        "batch_size": req.batch_size,
        "login_retry": req.login_retry,
        "start_from": req.start_from,
    }
    JOB_TASK = asyncio.create_task(run_job(accounts, cfg))
    return {"ok": True, "accounts": len(accounts), "event": req.event}


@app.post("/api/stop")
async def api_stop():
    if not STATE.running:
        raise HTTPException(400, "No job running")
    STATE.stop_flag = True
    if JOB_TASK and not JOB_TASK.done():
        JOB_TASK.cancel()
    return {"ok": True}


@app.get("/api/state")
async def api_state():
    snap = STATE.snapshot()
    snap["running"] = snap["running"] and not (JOB_TASK and JOB_TASK.done())
    return JSONResponse(snap)


@app.get("/api/results")
async def api_results():
    c = STATE.counters
    lines = [
        "=== FREE FIRE NARUTO MULTI-EVENT RESULTS ===",
        "Credit: KAWSAR | x64   |   Telegram: @kawsar449x",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"EVENT     : {STATE.event_label}",
        f"VERY RARE : {c['very_rare']}",
        f"RARE      : {c['rare']}",
        f"NORMAL    : {c['normal']}",
        f"Total     : {c['total_items']}",
        f"Accounts  : {STATE.accounts_total}",
        "",
        "=== HITS ===",
    ]
    if STATE.hits:
        lines += STATE.hits
    else:
        lines.append("No rare items found.")
    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=NARUTO_spins_summary.txt"})


@app.get("/api/results.json")
async def api_results_json():
    return JSONResponse({
        "counters": STATE.counters,
        "event": STATE.event_label,
        "items": list(STATE.items),
    })


# static assets (css/js)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)
