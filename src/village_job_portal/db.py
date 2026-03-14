from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import sqlite3


@dataclass(slots=True)
class WorkerRecord:
    name: str
    phone: str
    skill_slug: str
    skill_label: str
    village: str
    village_tag: str
    location_tag: str
    age: int = 28
    image_url: str = ""
    hourly_rate: float = 120.0
    daily_rate: float = 850.0
    available: int = 1
    working_start_time: str = "09:00"
    working_end_time: str = "18:00"
    next_free_at: str = "अभी उपलब्ध"
    jobs_completed: int = 0
    rating: float = 3.0


class WorkerDirectory:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self, seed: bool = False) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema_sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self.connect() as connection:
            connection.executescript(schema_sql)
            self._ensure_worker_columns(connection)
            self._ensure_auth_and_booking_tables(connection)
            self._seed_default_admin(connection)
            if seed:
                seed_sql = Path(__file__).with_name("seed.sql").read_text(encoding="utf-8")
                connection.executescript(seed_sql)

    def _ensure_worker_columns(self, connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(workers)")}
        required_columns = {
            "age": "ALTER TABLE workers ADD COLUMN age INTEGER NOT NULL DEFAULT 28",
            "image_url": "ALTER TABLE workers ADD COLUMN image_url TEXT NOT NULL DEFAULT ''",
            "hourly_rate": "ALTER TABLE workers ADD COLUMN hourly_rate REAL NOT NULL DEFAULT 120.0",
            "daily_rate": "ALTER TABLE workers ADD COLUMN daily_rate REAL NOT NULL DEFAULT 850.0",
            "working_start_time": "ALTER TABLE workers ADD COLUMN working_start_time TEXT NOT NULL DEFAULT '09:00'",
            "working_end_time": "ALTER TABLE workers ADD COLUMN working_end_time TEXT NOT NULL DEFAULT '18:00'",
            "next_free_at": "ALTER TABLE workers ADD COLUMN next_free_at TEXT NOT NULL DEFAULT 'अभी उपलब्ध'",
        }
        for column_name, statement in required_columns.items():
            if column_name not in columns:
                connection.execute(statement)

    def _ensure_auth_and_booking_tables(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                provider TEXT NOT NULL DEFAULT 'local',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_phone TEXT NOT NULL,
                booked_by_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'booked',
                notes TEXT NOT NULL DEFAULT '',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                progress_note TEXT NOT NULL DEFAULT 'काम शुरू नहीं हुआ',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(booked_by_user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_bookings_worker_phone ON bookings(worker_phone, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(booked_by_user_id, created_at DESC);
            """
        )
        self._ensure_booking_columns(connection)

    def _ensure_booking_columns(self, connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(bookings)")}
        required_columns = {
            "progress_percent": "ALTER TABLE bookings ADD COLUMN progress_percent INTEGER NOT NULL DEFAULT 0",
            "progress_note": "ALTER TABLE bookings ADD COLUMN progress_note TEXT NOT NULL DEFAULT 'काम शुरू नहीं हुआ'",
            "updated_at": "ALTER TABLE bookings ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''",
        }
        for column_name, statement in required_columns.items():
            if column_name not in columns:
                connection.execute(statement)
        connection.execute(
            "UPDATE bookings SET updated_at = created_at WHERE updated_at = ''"
        )

    def _seed_default_admin(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO users (full_name, email, phone, password_hash, role, provider)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "Village Admin",
                "admin@vjp.local",
                "9999999999",
                "admin123",
                "admin",
                "local",
            ),
        )

    def register_worker(self, record: WorkerRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO workers (
                    name, phone, skill_slug, skill_label, village, village_tag, location_tag,
                    age, image_url, hourly_rate, daily_rate, available, working_start_time,
                    working_end_time, next_free_at, jobs_completed, rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET
                    name = excluded.name,
                    skill_slug = excluded.skill_slug,
                    skill_label = excluded.skill_label,
                    village = excluded.village,
                    village_tag = excluded.village_tag,
                    location_tag = excluded.location_tag,
                    age = excluded.age,
                    image_url = excluded.image_url,
                    hourly_rate = excluded.hourly_rate,
                    daily_rate = excluded.daily_rate,
                    available = excluded.available,
                    working_start_time = excluded.working_start_time,
                    working_end_time = excluded.working_end_time,
                    next_free_at = excluded.next_free_at
                """,
                (
                    record.name,
                    record.phone,
                    record.skill_slug,
                    record.skill_label,
                    record.village,
                    record.village_tag,
                    record.location_tag,
                    record.age,
                    record.image_url,
                    record.hourly_rate,
                    record.daily_rate,
                    record.available,
                    record.working_start_time,
                    record.working_end_time,
                    record.next_free_at,
                    record.jobs_completed,
                    record.rating,
                ),
            )

    def search_workers(self, skill_slug: str, location_tag: str | None = None, limit: int = 3) -> list[sqlite3.Row]:
        params: list[object] = [skill_slug]
        location_boost = "1"
        if location_tag:
            location_boost = "CASE WHEN village_tag = ? OR location_tag = ? THEN 0 ELSE 1 END"
            params.extend([location_tag, location_tag])

        params.append(limit)
        with self.connect() as connection:
            cursor = connection.execute(
                f"""
                SELECT
                    name,
                    phone,
                    skill_label,
                    village,
                    age,
                    image_url,
                    hourly_rate,
                    daily_rate,
                    available,
                    working_start_time,
                    working_end_time,
                    next_free_at,
                    rating,
                    jobs_completed
                FROM workers
                WHERE skill_slug = ? AND available = 1
                ORDER BY {location_boost}, jobs_completed DESC, rating DESC, name ASC
                LIMIT ?
                """,
                params,
            )
            return list(cursor.fetchall())

    def list_workers(self, limit: int | None = None) -> list[sqlite3.Row]:
        query = """
            SELECT
                name,
                phone,
                skill_label,
                village,
                age,
                image_url,
                hourly_rate,
                daily_rate,
                available,
                working_start_time,
                working_end_time,
                next_free_at,
                rating,
                jobs_completed
            FROM workers
            ORDER BY available DESC, jobs_completed DESC, rating DESC, name ASC
        """
        params: list[object] = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.connect() as connection:
            cursor = connection.execute(query, params)
            return list(cursor.fetchall())

    def get_worker_profile(self, phone: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT
                    id,
                    name,
                    phone,
                    skill_slug,
                    skill_label,
                    village,
                    age,
                    image_url,
                    hourly_rate,
                    daily_rate,
                    working_start_time,
                    working_end_time,
                    next_free_at,
                    rating,
                    jobs_completed,
                    available
                FROM workers
                WHERE phone = ?
                """,
                (phone,),
            )
            return cursor.fetchone()

    def get_recent_work_history(self, worker_id: int, days: int = 60) -> list[sqlite3.Row]:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT
                    work_date,
                    client_name,
                    job_title,
                    hours_worked,
                    days_worked,
                    total_earned,
                    village,
                    notes
                FROM work_history
                WHERE worker_id = ? AND date(work_date) >= date('now', ?)
                ORDER BY date(work_date) DESC, id DESC
                """,
                (worker_id, f"-{days} day"),
            )
            return list(cursor.fetchall())

    def create_user(self, full_name: str, email: str, phone: str, password_hash: str, provider: str = "local") -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (full_name, email, phone, password_hash, role, provider)
                VALUES (?, ?, ?, ?, 'user', ?)
                """,
                (full_name, email.lower().strip(), phone.strip(), password_hash, provider),
            )
            return int(cursor.lastrowid)

    def get_user_by_email(self, email: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT id, full_name, email, phone, password_hash, role, provider FROM users WHERE email = ?",
                (email.lower().strip(),),
            )
            return cursor.fetchone()

    def get_user_by_id(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT id, full_name, email, phone, role, provider FROM users WHERE id = ?",
                (user_id,),
            )
            return cursor.fetchone()

    def create_session(self, user_id: int, hours_valid: int = 24) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours_valid)).isoformat()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
                (user_id, token, expires_at),
            )
        return token

    def get_user_by_session_token(self, token: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT u.id, u.full_name, u.email, u.phone, u.role, u.provider
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = ? AND s.expires_at > ?
                """,
                (token, datetime.now(timezone.utc).isoformat()),
            )
            return cursor.fetchone()

    def delete_session(self, token: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def create_booking(self, worker_phone: str, booked_by_user_id: int, notes: str = "") -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO bookings (
                    worker_phone,
                    booked_by_user_id,
                    status,
                    notes,
                    progress_percent,
                    progress_note,
                    updated_at
                )
                VALUES (?, ?, 'booked', ?, 0, 'काम शुरू नहीं हुआ', CURRENT_TIMESTAMP)
                """,
                (worker_phone, booked_by_user_id, notes.strip()),
            )
            return int(cursor.lastrowid)

    def update_booking_progress(self, booking_id: int, progress_percent: int, progress_note: str, status: str) -> None:
        progress_value = max(0, min(100, progress_percent))
        status_value = status.strip().lower()
        if status_value not in {"booked", "in_progress", "completed", "cancelled"}:
            status_value = "in_progress"

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE bookings
                SET progress_percent = ?,
                    progress_note = ?,
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (progress_value, progress_note.strip(), status_value, booking_id),
            )

    def get_booking_by_id(self, booking_id: int) -> sqlite3.Row | None:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT id, worker_phone, booked_by_user_id, status, notes,
                       progress_percent, progress_note, created_at, updated_at
                FROM bookings
                WHERE id = ?
                """,
                (booking_id,),
            )
            return cursor.fetchone()

    def set_worker_booking_status(self, worker_phone: str, is_free: bool, next_free_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE workers SET available = ?, next_free_at = ? WHERE phone = ?",
                (1 if is_free else 0, next_free_at, worker_phone),
            )

    def get_latest_booking_for_worker(self, worker_phone: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT b.id, b.worker_phone, b.status, b.notes,
                       b.progress_percent, b.progress_note, b.created_at, b.updated_at,
                       u.full_name AS booked_by_name, u.phone AS booked_by_phone
                FROM bookings b
                JOIN users u ON u.id = b.booked_by_user_id
                WHERE b.worker_phone = ?
                ORDER BY b.id DESC
                LIMIT 1
                """,
                (worker_phone,),
            )
            return cursor.fetchone()

    def list_recent_bookings(self, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT b.id, b.worker_phone, b.status, b.notes,
                       b.progress_percent, b.progress_note, b.created_at, b.updated_at,
                       u.full_name AS booked_by_name, u.phone AS booked_by_phone,
                       w.name AS worker_name, w.skill_label, w.village
                FROM bookings b
                JOIN users u ON u.id = b.booked_by_user_id
                LEFT JOIN workers w ON w.phone = b.worker_phone
                ORDER BY b.id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return list(cursor.fetchall())
