#!/usr/bin/env python3
"""
demo.py — End-to-end demonstration of the Village Job Portal SMS engine.

Run with:
    python demo.py
"""

import os
import tempfile

# Use a fresh temporary database so the demo is always reproducible
_demo_fd, _demo_db = tempfile.mkstemp(suffix=".db")
os.close(_demo_fd)  # Close the fd; SQLite will manage the file
os.environ["VJP_DB_PATH"] = _demo_db

from app.database import init_db, get_all_skills  # noqa: E402
from app.sms_handler import handle_incoming_sms    # noqa: E402

DEMO_REQUESTS = [
    # (sender_phone,        sms_message)
    ("+910000000001", "Need Tractor Mechanic in Sitapur"),
    ("+910000000002", "Mistri chahiye diwaar banwani hai"),
    ("+910000000003", "Plumber bhejo paani ka pipe leak hai"),
    ("+910000000004", "Fasal kaatne ke liye mazdoor chahiye in Hardoi"),
    ("+910000000005", "Bijli wala chahiye"),
    ("+910000000006", "Carpenter needed urgently"),
    ("+910000000007", "Need painter in Lakhimpur"),
    ("+910000000008", "Welder chahiye iron grill ke liye"),
    ("+910000000009", "Need astronaut"),        # unknown skill
    ("+910000000010", ""),                      # empty message
]


def _separator(title: str) -> None:
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def main() -> None:
    _separator("Village Job Portal — SMS Demo")
    print(f"Initialising database at: {_demo_db}")
    init_db(_demo_db)

    skills = get_all_skills(_demo_db)
    print(f"\nRegistered skills in DB ({len(skills)} total):")
    for s in skills:
        print(f"  • {s}")

    _separator("Processing Incoming SMS Requests")
    for phone, msg in DEMO_REQUESTS:
        display_msg = msg if msg else "(empty)"
        print(f"\n📱 From {phone}: \"{display_msg}\"")
        print("-" * 50)
        reply = handle_incoming_sms(phone, msg, db_path=_demo_db)
        print(reply)

    # Cleanup temp db
    try:
        os.remove(_demo_db)
    except OSError:
        pass


if __name__ == "__main__":
    main()
