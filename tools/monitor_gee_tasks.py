#!/usr/bin/env python3
"""List and (optionally) wait on Google Earth Engine export tasks.

Replaces the manual step of watching the Code Editor "Tasks" tab between the
export and download stages of the pipeline.

Examples:
  python3 tools/monitor_gee_tasks.py                      # recent tasks
  python3 tools/monitor_gee_tasks.py --filter agb_ --wait  # block until done
  python3 tools/monitor_gee_tasks.py --project my-gee-project --limit 50

Exit code is 0 when all matching tasks completed, 1 if any failed/cancelled.
"""
from __future__ import annotations

import argparse
import sys
import time

import ee

ACTIVE = {"READY", "RUNNING", "CANCEL_REQUESTED"}
FAILED = {"FAILED", "CANCELLED"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", default=None, help="GEE Cloud project (default: from earthengine config)")
    p.add_argument("--filter", default="", help="Only show tasks whose description contains this text")
    p.add_argument("--limit", type=int, default=30, help="Max tasks to show (default 30)")
    p.add_argument("--wait", action="store_true", help="Poll until no matching task is READY/RUNNING")
    p.add_argument("--interval", type=int, default=60, help="Polling interval in seconds (default 60)")
    return p.parse_args()


def matching_tasks(text: str, limit: int) -> list[dict]:
    tasks = [t for t in ee.data.getTaskList() if text in t.get("description", "")]
    return tasks[:limit]


def show(tasks: list[dict]) -> None:
    print(f"{'STATE':<17}{'DESCRIPTION':<60}ERROR")
    for t in tasks:
        print(f"{t.get('state', '?'):<17}{t.get('description', '')[:58]:<60}{t.get('error_message', '')}")


def main() -> int:
    args = parse_args()
    ee.Initialize(project=args.project) if args.project else ee.Initialize()
    while True:
        tasks = matching_tasks(args.filter, args.limit)
        show(tasks)
        active = [t for t in tasks if t.get("state") in ACTIVE]
        if not args.wait or not active:
            break
        print(f"\n{len(active)} task(s) still active; checking again in {args.interval}s...\n")
        time.sleep(args.interval)
    return 1 if any(t.get("state") in FAILED for t in tasks) else 0


if __name__ == "__main__":
    sys.exit(main())
