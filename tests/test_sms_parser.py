"""
tests/test_sms_parser.py — Unit tests for the SMS parsing engine.
"""

import os
import tempfile
import pytest

# Point tests at a fresh temp DB
_fd, _db = tempfile.mkstemp(suffix="_parser_test.db")
os.close(_fd)  # Close the fd; SQLite will manage the file
os.environ["VJP_DB_PATH"] = _db

from app.database import init_db
from app.sms_parser import parse_sms, extract_location


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db(_db)
    yield
    try:
        os.remove(_db)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# parse_sms
# ---------------------------------------------------------------------------

class TestParseSms:
    def test_tractor_mechanic_english(self):
        skill, phrase = parse_sms("Need Tractor Mechanic", _db)
        assert skill == "tractor mechanic"

    def test_tractor_keyword_alone(self):
        skill, phrase = parse_sms("Tractor kharab ho gaya", _db)
        assert skill == "tractor mechanic"

    def test_mechanic_keyword_alone(self):
        skill, phrase = parse_sms("mechanic chahiye", _db)
        assert skill == "tractor mechanic"

    def test_hindi_mistri(self):
        skill, phrase = parse_sms("Mistri chahiye diwaar banwani hai", _db)
        assert skill == "mason"

    def test_hindi_raj_mistri(self):
        skill, phrase = parse_sms("raj mistri bhejo", _db)
        assert skill == "mason"

    def test_plumber_english(self):
        skill, phrase = parse_sms("Need a plumber urgently", _db)
        assert skill == "plumber"

    def test_hindi_nal(self):
        skill, phrase = parse_sms("nal kharab hai paani nahi aa raha", _db)
        # "nal" or "paani" should map to plumber
        assert skill == "plumber"

    def test_electrician_bijli(self):
        skill, phrase = parse_sms("bijli nahi hai electrician chahiye", _db)
        assert skill == "electrician"

    def test_harvesting_labour(self):
        skill, phrase = parse_sms("fasal kaatne ke liye mazdoor chahiye", _db)
        assert skill == "harvesting labour"

    def test_carpenter(self):
        skill, phrase = parse_sms("Carpenter needed for door repair", _db)
        assert skill == "carpenter"

    def test_painter(self):
        skill, phrase = parse_sms("paint karna hai ghar mein", _db)
        assert skill == "painter"

    def test_welder(self):
        skill, phrase = parse_sms("welding kaam chahiye", _db)
        assert skill == "welder"

    def test_unknown_skill_returns_none(self):
        skill, phrase = parse_sms("Need astronaut immediately", _db)
        assert skill is None
        assert phrase is None

    def test_empty_message_returns_none(self):
        skill, phrase = parse_sms("", _db)
        assert skill is None

    def test_whitespace_message_returns_none(self):
        skill, phrase = parse_sms("   ", _db)
        assert skill is None

    def test_longest_match_wins(self):
        # "tractor mechanic" should win over just "mechanic"
        skill, phrase = parse_sms("tractor mechanic needed asap", _db)
        assert skill == "tractor mechanic"
        assert phrase == "tractor mechanic"

    def test_case_insensitive(self):
        skill, _ = parse_sms("NEED TRACTOR MECHANIC", _db)
        assert skill == "tractor mechanic"

    def test_mixed_case(self):
        skill, _ = parse_sms("Mistri Chahiye", _db)
        assert skill == "mason"


# ---------------------------------------------------------------------------
# extract_location
# ---------------------------------------------------------------------------

class TestExtractLocation:
    def test_in_keyword(self):
        loc = extract_location("Need Tractor Mechanic in Sitapur")
        assert loc == "Sitapur"

    def test_at_keyword(self):
        loc = extract_location("Plumber needed at Hardoi")
        assert loc == "Hardoi"

    def test_near_keyword(self):
        loc = extract_location("mason near Lakhimpur")
        assert loc == "Lakhimpur"

    def test_no_location_returns_none(self):
        loc = extract_location("Need Tractor Mechanic")
        assert loc is None

    def test_capitalised_output(self):
        loc = extract_location("need plumber in sitapur")
        assert loc == "Sitapur"
