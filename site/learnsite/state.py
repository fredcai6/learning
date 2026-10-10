"""The state database: reviews, lesson activity, card flags."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path

from fsrs import Card as FsrsCard, Rating, Scheduler

SCHEDULER = Scheduler()

# How far ahead a card still in its learning steps (minutes apart) may be
# shown when nothing else is due, so a short session can finish its steps.
LEARN_AHEAD = timedelta(minutes=20)


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


class State:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.executescript(files("learnsite").joinpath("schema.sql").read_text())

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    # --- lesson activity ------------------------------------------------------

    def record_event(self, learner: str, lesson_id: str, kind: str, item_id: str | None, result: str | None) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO lesson_event (learner, lesson_id, kind, item_id, result, at) VALUES (?,?,?,?,?,?)",
                       (learner, lesson_id, kind, item_id, result, iso(now())))

    def viewed_lessons(self, learner: str) -> set[str]:
        with self.connect() as db:
            rows = db.execute("SELECT DISTINCT lesson_id FROM lesson_event WHERE learner = ? AND kind = 'view'", (learner,))
            return {r["lesson_id"] for r in rows}

    def lesson_results(self, learner: str) -> dict[str, dict]:
        """Per lesson: the first answer to each quiz and the latest grade of each exercise."""
        out: dict[str, dict] = {}
        with self.connect() as db:
            rows = db.execute("SELECT lesson_id, kind, item_id, result FROM lesson_event "
                              "WHERE learner = ? AND kind IN ('quiz', 'exercise') ORDER BY id", (learner,))
            for r in rows:
                entry = out.setdefault(r["lesson_id"], {"quiz": {}, "exercise": {}})
                bucket = entry[r["kind"]]
                if r["kind"] == "quiz" and r["item_id"] in bucket:
                    continue          # first answer counts
                bucket[r["item_id"]] = r["result"]
        return out

    # --- reviews --------------------------------------------------------------

    def card_states(self, learner: str) -> dict[str, FsrsCard]:
        with self.connect() as db:
            rows = db.execute("SELECT card_id, fsrs FROM card_state WHERE learner = ?", (learner,))
            return {r["card_id"]: FsrsCard.from_json(r["fsrs"]) for r in rows}

    def new_cards_started_today(self, learner: str, day_start: datetime) -> int:
        """Cards whose first ever review fell after day_start."""
        with self.connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS n FROM (SELECT card_id, MIN(reviewed_at) AS first FROM review_log "
                "WHERE learner = ? GROUP BY card_id) WHERE first >= ?", (learner, iso(day_start))).fetchone()
            return row["n"]

    def review(self, learner: str, card_id: str, rating: int, at: datetime | None = None) -> FsrsCard:
        at = at or now()
        with self.connect() as db:
            row = db.execute("SELECT fsrs FROM card_state WHERE learner = ? AND card_id = ?", (learner, card_id)).fetchone()
            card = FsrsCard.from_json(row["fsrs"]) if row else FsrsCard()
            card, _ = SCHEDULER.review_card(card, Rating(rating), review_datetime=at)
            db.execute("INSERT INTO card_state (learner, card_id, fsrs, due) VALUES (?,?,?,?) "
                       "ON CONFLICT (learner, card_id) DO UPDATE SET fsrs = excluded.fsrs, due = excluded.due",
                       (learner, card_id, card.to_json(), iso(card.due)))
            db.execute("INSERT INTO review_log (learner, card_id, rating, reviewed_at) VALUES (?,?,?,?)",
                       (learner, card_id, rating, iso(at)))
        return card

    def reviews_since(self, learner: str, since: datetime) -> list[sqlite3.Row]:
        with self.connect() as db:
            return db.execute("SELECT card_id, rating, reviewed_at FROM review_log WHERE learner = ? AND reviewed_at >= ? "
                              "ORDER BY reviewed_at", (learner, iso(since))).fetchall()

    # --- flags ----------------------------------------------------------------

    def flag(self, learner: str, card_id: str, note: str | None) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO card_flag (learner, card_id, note, at) VALUES (?,?,?,?)",
                       (learner, card_id, note or None, iso(now())))

    def open_flags(self) -> set[str]:
        with self.connect() as db:
            return {r["card_id"] for r in db.execute("SELECT card_id FROM card_flag WHERE resolved_at IS NULL")}
