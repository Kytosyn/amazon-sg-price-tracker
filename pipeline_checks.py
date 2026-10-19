#!/usr/bin/env python3
"""Small helpers for .github/workflows/scrape.yml (no third-party deps).

Commands:
  python pipeline_checks.py meaningful-diff
      Compare data/products.json in the working tree against HEAD, ignoring
      ``exportedAt``. Writes ``changed=true|false`` to $GITHUB_OUTPUT so the
      auto-commit step can be skipped on export-only ticks that only bump the
      export timestamp.
  python pipeline_checks.py staleness [--max-age-hours 48]
      Emit a GitHub ``::warning::`` annotation when the newest product
      ``lastUpdated`` is older than the threshold. Never exits non-zero
      (warning only while ZenRows is paused).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JSON_PATH = Path("data/products.json")
VOLATILE_KEYS = ("exportedAt",)
DEFAULT_MAX_AGE_HOURS = 48.0


def strip_volatile(doc: Any) -> Any:
    if isinstance(doc, dict):
        return {k: v for k, v in doc.items() if k not in VOLATILE_KEYS}
    return doc


def is_meaningful_change(old: Any, new: Any) -> bool:
    """True when the export differs in anything other than ``exportedAt``."""
    return strip_volatile(old) != strip_volatile(new)


def _head_json(path: Path) -> Any | None:
    try:
        raw = subprocess.run(
            ["git", "show", f"HEAD:{path.as_posix()}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _write_output(key: str, value: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    print(f"{key}={value}")


def cmd_meaningful_diff() -> int:
    if not JSON_PATH.exists():
        _write_output("changed", "true")
        return 0
    new = json.loads(JSON_PATH.read_text())
    old = _head_json(JSON_PATH)
    if old is None:
        changed = True
    else:
        changed = is_meaningful_change(old, new)
    if not changed:
        print("products.json differs from HEAD only in exportedAt (or not at all) — skipping commit.")
    _write_output("changed", "true" if changed else "false")
    return 0


def parse_ts(value: Any) -> datetime | None:
    """Parse export timestamps. Naive values are runner-local UTC."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def staleness_hours(doc: Any, now: datetime | None = None) -> float | None:
    if not isinstance(doc, dict):
        return None
    newest = parse_ts(doc.get("lastUpdated"))
    if newest is None:
        stamps = [parse_ts(p.get("timestamp")) for p in doc.get("products", []) if isinstance(p, dict)]
        stamps = [s for s in stamps if s is not None]
        newest = max(stamps) if stamps else None
    if newest is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (now - newest).total_seconds() / 3600.0


def cmd_staleness(max_age_hours: float) -> int:
    if not JSON_PATH.exists():
        print("::warning title=DiskPrices data missing::data/products.json not found")
        return 0
    doc = json.loads(JSON_PATH.read_text())
    age = staleness_hours(doc)
    if age is None:
        print("::warning title=DiskPrices data age unknown::no lastUpdated/timestamp in products.json")
        return 0
    last = doc.get("lastUpdated")
    print(f"newest product lastUpdated={last} age_hours={age:.1f} threshold={max_age_hours:g}")
    if age > max_age_hours:
        print(
            f"::warning title=DiskPrices data stale::newest product lastUpdated={last} "
            f"is {age:.0f}h old (> {max_age_hours:g}h). Scrapers paused or failing?"
        )
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "meaningful-diff":
        return cmd_meaningful_diff()
    if cmd == "staleness":
        max_age = DEFAULT_MAX_AGE_HOURS
        if "--max-age-hours" in argv:
            try:
                max_age = float(argv[argv.index("--max-age-hours") + 1])
            except (IndexError, ValueError):
                pass
        return cmd_staleness(max_age)
    print(f"unknown command {cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
