"""
Daily automatic run of the watch agent. A loop wakes every 15 minutes and starts a run for each
doctor who has interests and has had no (non-failed) real run in the last 20 hours, once the
local time is past WATCH_HOUR. Because it checks "last 20 h" instead of a fixed clock time, a
laptop that was off at 07:00 simply catches up when the backend next starts.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from llm import ENABLED as LLM_ENABLED
from watch_agent import WatchBusy, run_watch, start_run

log = logging.getLogger("uvicorn.error")

ENABLED = os.environ.get("WATCH_AUTO", "0") == "1"      # off by default: enable on ONE machine only
START_HOUR = int(os.environ.get("WATCH_HOUR", "7"))     # server local time
CHECK_EVERY = 15 * 60
MIN_GAP_H = 20
RETRY_AFTER_FAIL_H = 3
DAYS = 14


def _due(sb, doctor_id: str) -> bool:
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=MIN_GAP_H)).isoformat()
    rows = (sb.table("agent_runs").select("status, created_at")
            .eq("doctor_id", doctor_id).eq("agent", "watch").eq("dry_run", False)
            .gte("created_at", since).execute().data)
    for r in rows:
        if r["status"] != "failed":
            return False                                   # running, completed or stopped: done for today
        t = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        if now - t < timedelta(hours=RETRY_AFTER_FAIL_H):
            return False                                   # failed recently: wait before retrying
    return True


def tick(sb):
    if not LLM_ENABLED or datetime.now().hour < START_HOUR:
        return
    doctors = sb.table("profiles").select("id, interests").in_("role", ["doctor", "admin"]).execute().data
    for d in doctors:
        if not d.get("interests") or not _due(sb, d["id"]):
            continue
        try:
            run_id = start_run(sb, d["id"], False)
        except WatchBusy:
            continue
        log.info("watch agent: automatic run for %s", d["id"])
        run_watch(sb, run_id, d["id"], False, DAYS)        # one doctor at a time (single local model)


async def loop(sb):
    await asyncio.sleep(30)                                # let the server finish starting
    while True:
        try:
            await asyncio.to_thread(tick, sb)
        except Exception:
            log.warning("watch scheduler tick failed", exc_info=True)
        await asyncio.sleep(CHECK_EVERY)