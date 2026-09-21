"""One-off, idempotent migration: make every LunaKey plan match the provider.

LunaKey only provides Locket Gold 1 year (category ``yearly``, 365 days). Any
LunaKey plan stored with another category (e.g. ``month`` — which is the shop's
warranty duration, not a provider category) or another Gold duration cannot be
activated and must be corrected.

Safety:
- Dry-run by default (prints changes, writes nothing).
- Only touches rows where ``activation_provider = 'lunakey'``.
- Never touches historical orders: ``activation_orders`` snapshots are immutable.
- Run with ``--apply`` to write.

Usage (from the backend directory, with the production venv):

    /opt/locket-gold/backend/.venv/bin/python migrate_lunakey_plans.py          # dry-run
    /opt/locket-gold/backend/.venv/bin/python migrate_lunakey_plans.py --apply  # write
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from locket import db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write changes (default: dry-run, no writes)")
    args = parser.parse_args()

    db.init()
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT id, name, slug, provider_category, duration_days, is_active "
        "FROM plans WHERE activation_provider = 'lunakey' ORDER BY id"
    ).fetchall()

    if not rows:
        print("No LunaKey plans found. Nothing to do.")
        return 0

    changed = 0
    for row in rows:
        category = (row["provider_category"] or "").strip().lower()
        duration = int(row["duration_days"] or 0)
        needs_fix = category != "yearly" or duration != 365
        target = "yearly/365" if needs_fix else "already ok"
        print(
            f"plan #{row['id']} {row['slug']!r}: "
            f"category={row['provider_category']!r} duration_days={duration} "
            f"active={row['is_active']} -> {target}"
        )
        if needs_fix and args.apply:
            conn.execute(
                "UPDATE plans SET provider_category = 'yearly', duration_days = 365, "
                "updated_at = ? WHERE id = ?",
                (time.time(), row["id"]),
            )
            changed += 1

    if args.apply:
        conn.commit()
        print(f"Applied to {changed} plan(s).")
    else:
        print("Dry-run only. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
