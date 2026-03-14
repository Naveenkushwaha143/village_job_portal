"""
sms_handler.py — Orchestrator that ties the parser, database, and response
                 formatter together.

Usage (library)
---------------
    from app.sms_handler import handle_incoming_sms

    response = handle_incoming_sms(
        requester_phone="+919999999999",
        message="Need Tractor Mechanic in Sitapur",
    )
    print(response)

Usage (webhook / CLI)
---------------------
    See demo.py in the project root.
"""

from typing import Optional

from app.database import find_workers, log_request
from app.sms_parser import extract_location, parse_sms

# ---------------------------------------------------------------------------
# Response templates
# ---------------------------------------------------------------------------

_FOUND_HEADER = (
    "Village Job Portal\n"
    "Aapke liye {count} {skill} mil{suffix}:\n"
    "---\n"
)
_WORKER_LINE = "{rank}. {name} ({location}) - {phone} [Rating: {rating}/5]"
_NOT_FOUND = (
    "Village Job Portal\n"
    "Sorry, abhi koi '{skill}' available nahi hai.\n"
    "Thodi der baad dobara try karein."
)
_UNKNOWN_SKILL = (
    "Village Job Portal\n"
    "Humein samajh nahi aaya aap kise dhundh rahe hain.\n"
    "Example SMS bhejein: 'Need Tractor Mechanic' ya 'Mistri chahiye'."
)

MAX_RESULTS = 3


def handle_incoming_sms(
    requester_phone: str,
    message: str,
    db_path: Optional[str] = None,
) -> str:
    """
    Process an incoming SMS and return the reply text.

    Steps
    -----
    1. Parse the message to extract skill and optional location.
    2. Query the database for available workers.
    3. Format a human-readable SMS reply.
    4. Log the request + response in sms_requests.
    """
    skill, matched_phrase = parse_sms(message, db_path)
    location = extract_location(message)

    if not skill:
        response = _UNKNOWN_SKILL
        log_request(requester_phone, message, None, response, db_path)
        return response

    workers = find_workers(skill, location, limit=MAX_RESULTS, db_path=db_path)

    if not workers:
        response = _NOT_FOUND.format(skill=skill)
    else:
        lines = [
            _FOUND_HEADER.format(
                count=len(workers),
                skill=skill,
                suffix="e" if len(workers) > 1 else "a",
            )
        ]
        for rank, w in enumerate(workers, start=1):
            lines.append(
                _WORKER_LINE.format(
                    rank=rank,
                    name=w["name"],
                    location=w["location"],
                    phone=w["phone"],
                    rating=w["rating"],
                )
            )
        response = "\n".join(lines)

    log_request(requester_phone, message, skill, response, db_path)
    return response
