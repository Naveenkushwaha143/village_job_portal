"""
tests/test_database.py — Unit tests for database helpers.
"""

import os
import tempfile
import pytest

_fd, _db = tempfile.mkstemp(suffix="_db_test.db")
os.close(_fd)  # Close the fd; SQLite will manage the file
os.environ["VJP_DB_PATH"] = _db

from app.database import (
    init_db,
    resolve_skill,
    find_workers,
    log_request,
    get_all_skills,
    set_worker_availability,
    get_connection,
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db(_db)
    yield
    try:
        os.remove(_db)
    except OSError:
        pass


class TestInitDb:
    def test_workers_seeded(self):
        conn = get_connection(_db)
        count = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
        conn.close()
        assert count > 0

    def test_skill_aliases_seeded(self):
        conn = get_connection(_db)
        count = conn.execute("SELECT COUNT(*) FROM skill_aliases").fetchone()[0]
        conn.close()
        assert count > 0

    def test_idempotent(self):
        """Calling init_db twice should not duplicate rows."""
        conn = get_connection(_db)
        before = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
        conn.close()
        init_db(_db)
        conn = get_connection(_db)
        after = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
        conn.close()
        assert before == after


class TestResolveSkill:
    def test_known_alias(self):
        assert resolve_skill("mistri", _db) == "mason"

    def test_tractor_alias(self):
        assert resolve_skill("tractor", _db) == "tractor mechanic"

    def test_full_phrase(self):
        assert resolve_skill("tractor mechanic", _db) == "tractor mechanic"

    def test_unknown_returns_none(self):
        assert resolve_skill("astronaut", _db) is None

    def test_case_insensitive_input(self):
        # resolve_skill lower-cases its input before querying, so uppercase works
        result = resolve_skill("MISTRI", _db)
        assert result == "mason"


class TestFindWorkers:
    def test_returns_up_to_three(self):
        workers = find_workers("tractor mechanic", db_path=_db)
        assert 1 <= len(workers) <= 3

    def test_all_have_correct_skill(self):
        for w in find_workers("mason", db_path=_db):
            assert w["skill"] == "mason"

    def test_ordered_by_rating(self):
        workers = find_workers("mason", db_path=_db)
        ratings = [w["rating"] for w in workers]
        assert ratings == sorted(ratings, reverse=True)

    def test_location_preference(self):
        workers = find_workers("mason", location="Sitapur", db_path=_db)
        # First result should be from Sitapur when one exists
        assert workers[0]["location"].lower() == "sitapur"

    def test_unknown_skill_returns_empty(self):
        workers = find_workers("astronaut", db_path=_db)
        assert workers == []

    def test_limit_respected(self):
        workers = find_workers("harvesting labour", limit=2, db_path=_db)
        assert len(workers) <= 2

    def test_unavailable_workers_excluded(self):
        # "Dinesh Singh" (tractor mechanic, Sitapur) is seeded as unavailable
        workers = find_workers("tractor mechanic", db_path=_db)
        phones = [w["phone"] for w in workers]
        assert "+919876543212" not in phones  # Dinesh Singh is unavailable


class TestLogRequest:
    def test_inserts_row(self):
        row_id = log_request("+910000000001", "Need plumber", "plumber", "reply", _db)
        assert isinstance(row_id, int) and row_id > 0

    def test_row_retrievable(self):
        log_request("+910000000002", "mistri chahiye", "mason", "reply text", _db)
        conn = get_connection(_db)
        row = conn.execute(
            "SELECT * FROM sms_requests WHERE requester_phone = ?",
            ("+910000000002",),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["parsed_skill"] == "mason"


class TestGetAllSkills:
    def test_returns_list(self):
        skills = get_all_skills(_db)
        assert isinstance(skills, list)
        assert len(skills) > 0

    def test_contains_known_skills(self):
        skills = get_all_skills(_db)
        assert "tractor mechanic" in skills
        assert "mason" in skills
        assert "plumber" in skills


class TestSetWorkerAvailability:
    def test_mark_unavailable(self):
        # Ramesh Kumar (+919876543210) is available by default
        result = set_worker_availability("+919876543210", False, _db)
        assert result is True
        conn = get_connection(_db)
        row = conn.execute(
            "SELECT is_available FROM workers WHERE phone = ?",
            ("+919876543210",),
        ).fetchone()
        conn.close()
        assert row["is_available"] == 0

    def test_mark_available_again(self):
        set_worker_availability("+919876543210", True, _db)
        conn = get_connection(_db)
        row = conn.execute(
            "SELECT is_available FROM workers WHERE phone = ?",
            ("+919876543210",),
        ).fetchone()
        conn.close()
        assert row["is_available"] == 1

    def test_unknown_phone_returns_false(self):
        result = set_worker_availability("+910000000000", True, _db)
        assert result is False
