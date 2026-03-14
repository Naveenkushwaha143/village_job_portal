"""
tests/test_sms_handler.py — Integration tests for the end-to-end SMS handler.
"""

import os
import tempfile
import pytest

_fd, _db = tempfile.mkstemp(suffix="_handler_test.db")
os.close(_fd)  # Close the fd; SQLite will manage the file
os.environ["VJP_DB_PATH"] = _db

from app.database import init_db, get_connection
from app.sms_handler import handle_incoming_sms


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db(_db)
    yield
    try:
        os.remove(_db)
    except OSError:
        pass


class TestHandleIncomingSms:
    def test_returns_string(self):
        result = handle_incoming_sms("+919999000001", "Need tractor mechanic", _db)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_found_workers_contains_header(self):
        result = handle_incoming_sms("+919999000002", "Need tractor mechanic", _db)
        assert "Village Job Portal" in result

    def test_found_workers_contains_phone_numbers(self):
        result = handle_incoming_sms("+919999000003", "Need plumber", _db)
        assert "+91" in result  # at least one phone number in response

    def test_found_workers_respects_limit(self):
        result = handle_incoming_sms("+919999000004", "Need mason", _db)
        # Response should list at most 3 workers (lines starting with 1. 2. 3.)
        lines_with_rank = [l for l in result.splitlines() if l.startswith(("1.", "2.", "3."))]
        assert 1 <= len(lines_with_rank) <= 3

    def test_unknown_skill_returns_help_message(self):
        result = handle_incoming_sms("+919999000005", "Need astronaut", _db)
        assert "samajh nahi" in result.lower() or "example" in result.lower()

    def test_empty_message_returns_help_message(self):
        result = handle_incoming_sms("+919999000006", "", _db)
        assert "example" in result.lower() or "samajh nahi" in result.lower()

    def test_hindi_message_works(self):
        result = handle_incoming_sms("+919999000007", "Mistri chahiye", _db)
        assert "Village Job Portal" in result
        assert "mason" in result.lower()

    def test_request_logged(self):
        phone = "+919999000008"
        handle_incoming_sms(phone, "Need welder urgently", _db)
        conn = get_connection(_db)
        row = conn.execute(
            "SELECT * FROM sms_requests WHERE requester_phone = ?",
            (phone,),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["parsed_skill"] == "welder"

    def test_location_filters_results(self):
        result_sitapur = handle_incoming_sms(
            "+919999000009", "Need mason in Sitapur", _db
        )
        # Sitapur workers should appear before workers from other locations
        assert "Sitapur" in result_sitapur

    def test_not_found_skill_returns_sorry_message(self):
        """If a known skill has no available workers, return the 'not found' reply."""
        # Mark all painters unavailable
        conn = get_connection(_db)
        conn.execute("UPDATE workers SET is_available = 0 WHERE skill = 'painter'")
        conn.commit()
        conn.close()

        result = handle_incoming_sms("+919999000010", "Need painter", _db)
        assert "available nahi" in result.lower() or "sorry" in result.lower()

        # Restore
        conn = get_connection(_db)
        conn.execute("UPDATE workers SET is_available = 1 WHERE skill = 'painter'")
        conn.commit()
        conn.close()
