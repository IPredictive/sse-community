"""Keep checking Shanghai Composite feeds after close until today's bar is available.

The workflow invokes this once after the market close. It retries inside one
GitHub Actions run, rather than depending on many independently queued cron runs.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, time as daytime
from zoneinfo import ZoneInfo

from data import fetch_sse

TZ = ZoneInfo("Asia/Shanghai")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-seconds", type=int, default=600)
    parser.add_argument("--deadline", default="17:35")
    args = parser.parse_args()

    now = datetime.now(TZ)
    if now.weekday() >= 5:
        print("[refresh] Weekend: no post-close refresh required.")
        return 0

    deadline_hour, deadline_minute = map(int, args.deadline.split(":"))
    deadline = now.replace(
        hour=deadline_hour, minute=deadline_minute, second=0, microsecond=0
    )
    if now > deadline:
        deadline = now

    expected_date = now.date().isoformat()
    attempt = 0
    while True:
        attempt += 1
        checked_at = datetime.now(TZ).isoformat(timespec="seconds")
        print(f"[refresh] attempt={attempt} checked_at={checked_at} expected={expected_date}")
        try:
            df = fetch_sse()
            latest = str(df["date"].max())[:10]
            if latest == expected_date:
                print(
                    f"[refresh] SUCCESS: latest_date={latest}; "
                    f"rows={len(df)}; attempts={attempt}"
                )
                return 0
            print(f"[refresh] Not current yet: latest_date={latest}")
        except Exception as exc:
            print(f"[refresh] Feed not ready: {type(exc).__name__}: {exc}")

        now = datetime.now(TZ)
        if now >= deadline:
            print(
                f"[refresh] FAILED: no current-day market bar by "
                f"{deadline.isoformat(timespec='minutes')}; refusing stale publish."
            )
            return 1

        remaining = (deadline - now).total_seconds()
        sleep_for = min(max(1, args.interval_seconds), remaining)
        print(f"[refresh] retrying in {int(sleep_for)} seconds")
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(main())
