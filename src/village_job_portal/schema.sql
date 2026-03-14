PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    skill_slug TEXT NOT NULL,
    skill_label TEXT NOT NULL,
    village TEXT NOT NULL,
    village_tag TEXT NOT NULL,
    location_tag TEXT NOT NULL,
    age INTEGER NOT NULL DEFAULT 28,
    image_url TEXT NOT NULL DEFAULT '',
    hourly_rate REAL NOT NULL DEFAULT 120.0,
    daily_rate REAL NOT NULL DEFAULT 850.0,
    available INTEGER NOT NULL DEFAULT 1,
    working_start_time TEXT NOT NULL DEFAULT '09:00',
    working_end_time TEXT NOT NULL DEFAULT '18:00',
    next_free_at TEXT NOT NULL DEFAULT '18:00',
    jobs_completed INTEGER NOT NULL DEFAULT 0,
    rating REAL NOT NULL DEFAULT 3.0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workers_skill_availability
    ON workers (skill_slug, available, village_tag);

CREATE INDEX IF NOT EXISTS idx_workers_location
    ON workers (location_tag);

CREATE TABLE IF NOT EXISTS work_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    work_date TEXT NOT NULL,
    client_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    hours_worked REAL NOT NULL DEFAULT 0,
    days_worked REAL NOT NULL DEFAULT 0,
    total_earned REAL NOT NULL DEFAULT 0,
    village TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(worker_id) REFERENCES workers(id) ON DELETE CASCADE,
    UNIQUE(worker_id, work_date, client_name, job_title)
);

CREATE INDEX IF NOT EXISTS idx_work_history_worker_date
    ON work_history (worker_id, work_date DESC);

CREATE TRIGGER IF NOT EXISTS workers_updated_at
AFTER UPDATE ON workers
FOR EACH ROW
BEGIN
    UPDATE workers
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;