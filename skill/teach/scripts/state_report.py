#!/usr/bin/env python3
"""What a learner has done on the website since the vault last taught them.

Usage:
  python3 state_report.py LEARNER [--vault DIR] [--days 30]
  python3 state_report.py --resolve FLAG_ID [--vault DIR]

Reads the state database named by `state_db` in vault.toml: lessons opened,
quiz and exercise results, review performance by card and node, and cards
flagged as bad. `--resolve` marks a flag done once its card is rewritten.
Standard library only.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def connect(vault: Path) -> sqlite3.Connection:
    settings = tomllib.loads((vault / "vault.toml").read_text(encoding="utf-8"))
    if not settings.get("state_db"):
        raise SystemExit("vault.toml sets no state_db: the website has not been set up for this vault")
    path = Path(settings["state_db"]).expanduser()
    if not path.is_file():
        raise SystemExit(f"no state database yet at {path}: nothing has been done on the website")
    db = sqlite3.connect(f"file:{path}?mode=rw", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def card_nodes(vault: Path) -> dict[str, list[str]]:
    out = {}
    for path in (vault / "topics").glob("*/cards/*.toml"):
        topic = path.parent.parent.name
        for card in tomllib.loads(path.read_text(encoding="utf-8")).get("card", []):
            out[f"{topic}/{path.stem}/{card['id']}"] = card.get("nodes", [])
    return out


def report(db: sqlite3.Connection, vault: Path, learner: str, days: int) -> None:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    print(f"# {learner}: website activity, last {days} days\n")

    print("## Lessons")
    rows = db.execute("SELECT lesson_id, MIN(at) AS first, MAX(at) AS last FROM lesson_event "
                      "WHERE learner = ? AND kind = 'view' AND at >= ? GROUP BY lesson_id ORDER BY first",
                      (learner, since)).fetchall()
    results = defaultdict(lambda: {"quiz": {}, "exercise": {}})
    for r in db.execute("SELECT lesson_id, kind, item_id, result FROM lesson_event WHERE learner = ? "
                        "AND kind IN ('quiz', 'exercise') AND at >= ? ORDER BY id", (learner, since)):
        bucket = results[r["lesson_id"]][r["kind"]]
        if r["kind"] == "quiz" and r["item_id"] in bucket:
            continue
        bucket[r["item_id"]] = r["result"]
    if not rows:
        print("- none opened")
    for r in rows:
        res = results[r["lesson_id"]]
        quiz = res["quiz"]
        wrong = [k for k, v in quiz.items() if v == "wrong"]
        weak = [f"{k} ({v})" for k, v in res["exercise"].items() if v != "got"]
        line = f"- {r['lesson_id']}: opened {r['first'][:10]}"
        if quiz:
            line += f"; quizzes {len(quiz) - len(wrong)}/{len(quiz)} right first time"
        if wrong:
            line += f"; missed: {', '.join(wrong)}"
        if res["exercise"]:
            line += f"; exercises {Counter(res['exercise'].values()).get('got', 0)}/{len(res['exercise'])} got"
        if weak:
            line += f"; not yet: {', '.join(weak)}"
        print(line)

    print("\n## Reviews")
    reviews = db.execute("SELECT card_id, rating FROM review_log WHERE learner = ? AND reviewed_at >= ?",
                         (learner, since)).fetchall()
    if not reviews:
        print("- none")
    else:
        recalled = sum(1 for r in reviews if r["rating"] >= 2)
        print(f"- {len(reviews)} reviews; recalled {recalled}/{len(reviews)}")
        lapses = Counter(r["card_id"] for r in reviews if r["rating"] == 1)
        nodes = card_nodes(vault)
        by_node = Counter()
        for cid, n in lapses.items():
            for node in nodes.get(cid, ["(card no longer in the vault)"]):
                by_node[node] += n
        if lapses:
            print("- forgotten (rated Again), most first:")
            for cid, n in lapses.most_common(15):
                print(f"  - {cid} ×{n}")
            print("- forgetting by node: " + ", ".join(f"{node} ×{n}" for node, n in by_node.most_common()))

    print("\n## Flagged cards (rewrite, then resolve with --resolve ID)")
    flags = db.execute("SELECT id, learner, card_id, note, at FROM card_flag WHERE resolved_at IS NULL ORDER BY at").fetchall()
    if not flags:
        print("- none")
    for f in flags:
        note = f": {f['note']}" if f["note"] else ""
        print(f"- [{f['id']}] {f['card_id']} (by {f['learner']}, {f['at'][:10]}){note}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("learner", nargs="?")
    parser.add_argument("--vault", default=".")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--resolve", type=int, metavar="FLAG_ID")
    args = parser.parse_args()
    vault = Path(args.vault).resolve()
    db = connect(vault)
    if args.resolve is not None:
        with db:
            n = db.execute("UPDATE card_flag SET resolved_at = ? WHERE id = ? AND resolved_at IS NULL",
                           (datetime.now(timezone.utc).isoformat(), args.resolve)).rowcount
        print(f"resolved flag {args.resolve}" if n else f"no open flag {args.resolve}")
        return 0 if n else 1
    if not args.learner:
        parser.error("name a learner, or pass --resolve")
    report(db, vault, args.learner, args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
