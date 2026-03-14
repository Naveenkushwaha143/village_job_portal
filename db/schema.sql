-- Village Job Portal - SMS-based Skill & Labor Directory
-- Schema for SQLite database

CREATE TABLE IF NOT EXISTS workers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    phone       TEXT    NOT NULL UNIQUE,
    skill       TEXT    NOT NULL,          -- primary skill (normalised, lowercase)
    location    TEXT    NOT NULL,          -- village / area name
    is_available INTEGER NOT NULL DEFAULT 1, -- 1 = available, 0 = busy
    rating      REAL    NOT NULL DEFAULT 5.0, -- 1.0 – 5.0
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Alternate names / synonyms mapped to the canonical skill name stored in workers
CREATE TABLE IF NOT EXISTS skill_aliases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alias       TEXT NOT NULL UNIQUE,   -- keyword that may appear in an SMS
    skill       TEXT NOT NULL           -- canonical skill name (matches workers.skill)
);

-- Log every incoming SMS request and the response that was generated
CREATE TABLE IF NOT EXISTS sms_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_phone TEXT NOT NULL,
    raw_message     TEXT NOT NULL,
    parsed_skill    TEXT,               -- skill that was extracted from the message
    response_text   TEXT,               -- SMS that was sent back
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for fast look-ups
CREATE INDEX IF NOT EXISTS idx_workers_skill       ON workers (skill);
CREATE INDEX IF NOT EXISTS idx_workers_location    ON workers (location);
CREATE INDEX IF NOT EXISTS idx_workers_available   ON workers (is_available);
CREATE INDEX IF NOT EXISTS idx_skill_aliases_alias ON skill_aliases (alias);
