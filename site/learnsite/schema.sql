-- The state database: everything learners do, as opposed to what the vault
-- teaches. Shared on disk by the website, the tutor bot, and the teach skill
-- (scripts/state_report.py). Learner ids are the keys of learners.toml.

PRAGMA journal_mode = WAL;

-- One row per learner per card they have started reviewing. `fsrs` is the
-- fsrs.Card as JSON; `due` is copied out of it so the queue is one query.
CREATE TABLE IF NOT EXISTS card_state (
    learner   TEXT NOT NULL,
    card_id   TEXT NOT NULL,          -- <topic>/<cards file stem>/<card id>
    fsrs      TEXT NOT NULL,
    due       TEXT NOT NULL,          -- ISO 8601, UTC
    PRIMARY KEY (learner, card_id)
);

CREATE TABLE IF NOT EXISTS review_log (
    id          INTEGER PRIMARY KEY,
    learner     TEXT NOT NULL,
    card_id     TEXT NOT NULL,
    rating      INTEGER NOT NULL,     -- 1 again, 2 hard, 3 good, 4 easy
    reviewed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS review_log_learner ON review_log (learner, reviewed_at);

-- Lesson activity: a view, a quiz answer, a self-graded exercise.
CREATE TABLE IF NOT EXISTS lesson_event (
    id         INTEGER PRIMARY KEY,
    learner    TEXT NOT NULL,
    lesson_id  TEXT NOT NULL,         -- <topic>/<file stem>, the page's lesson-id
    kind       TEXT NOT NULL,         -- view | quiz | exercise
    item_id    TEXT,                  -- the quiz or exercise data-id
    result     TEXT,                  -- quiz: right | wrong; exercise: got | partly | missed
    at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lesson_event_learner ON lesson_event (learner, lesson_id);

-- A learner saying a card is bad. The teach skill rewrites it and resolves.
CREATE TABLE IF NOT EXISTS card_flag (
    id          INTEGER PRIMARY KEY,
    learner     TEXT NOT NULL,
    card_id     TEXT NOT NULL,
    note        TEXT,
    at          TEXT NOT NULL,
    resolved_at TEXT
);
