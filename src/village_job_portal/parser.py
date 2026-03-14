from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "tractor_mechanic": (
        "tractor mechanic",
        "tractor repair",
        "diesel mechanic",
        "engine mechanic",
        "tractor",
        "mechanic",
        "ट्रैक्टर मैकेनिक",
        "ट्रैक्टर रिपेयर",
    ),
    "mason": (
        "mason",
        "raj mistri",
        "mistri",
        "wall builder",
        "brick work",
        "राज मिस्त्री",
        "मिस्त्री",
    ),
    "plumber": ("plumber", "pipe repair", "water line", "प्लम्बर", "प्लंबर", "नल मरम्मत"),
    "electrician": ("electrician", "wiring", "light repair", "इलेक्ट्रीशियन", "बिजली मिस्त्री"),
    "farm_labor": (
        "farm labor",
        "farm labour",
        "harvesting labor",
        "harvesting labour",
        "mazdoor",
        "labor",
        "labour",
        "खेती मजदूर",
        "मजदूर",
        "खेत मजदूर",
    ),
    "welder": ("welder", "welding", "वेल्डर", "वेल्डिंग"),
    "carpenter": ("carpenter", "wood work", "furniture repair", "बढ़ई", "कारपेंटर"),
    "painter": ("painter", "paint work", "wall paint", "पेंटर", "रंगाई"),
    "tile_fitter": ("tile fitter", "tiles work", "floor tiles", "टाइल फिटर", "टाइल्स का काम"),
    "borewell_technician": ("borewell", "submersible", "water motor", "बोरवेल", "समर्सिबल", "मोटर रिपेयर"),
    "pump_mechanic": ("pump mechanic", "irrigation pump", "pump repair", "पंप मैकेनिक", "पंप रिपेयर"),
    "driver": ("driver", "tractor driver", "pickup driver", "ड्राइवर", "ट्रैक्टर चालक"),
    "cattle_helper": ("dairy helper", "animal care", "cattle helper", "पशुपालन सहायक", "दूध डेयरी सहायक"),
    "house_help": ("house help", "maid", "cleaning", "घरेलू सहायक", "कामवाली", "सफाई"),
    "tailor": ("tailor", "stitching", "silai", "टेलर", "सिलाई"),
    "cook": ("cook", "rasoi", "tiffin", "रसोइया", "कुक"),
    "mobile_repair": ("mobile repair", "phone repair", "मोबाइल रिपेयर", "फोन रिपेयर"),
}

SKILL_LABELS: dict[str, str] = {
    "tractor_mechanic": "Tractor Mechanic",
    "mason": "Mason",
    "plumber": "Plumber",
    "electrician": "Electrician",
    "farm_labor": "Farm Labor",
    "welder": "Welder",
    "carpenter": "Carpenter",
    "painter": "Painter",
    "tile_fitter": "Tile Fitter",
    "borewell_technician": "Borewell Technician",
    "pump_mechanic": "Pump Mechanic",
    "driver": "Driver",
    "cattle_helper": "Cattle Helper",
    "house_help": "House Help",
    "tailor": "Tailor",
    "cook": "Cook",
    "mobile_repair": "Mobile Repair",
}

SKILL_HINDI_LABELS: dict[str, str] = {
    "Tractor Mechanic": "ट्रैक्टर मैकेनिक",
    "Mason": "राज मिस्त्री",
    "Plumber": "प्लम्बर",
    "Electrician": "इलेक्ट्रीशियन",
    "Farm Labor": "खेती मजदूर",
    "Welder": "वेल्डर",
    "Carpenter": "बढ़ई",
    "Painter": "पेंटर",
    "Tile Fitter": "टाइल फिटर",
    "Borewell Technician": "बोरवेल तकनीशियन",
    "Pump Mechanic": "पंप मैकेनिक",
    "Driver": "ड्राइवर",
    "Cattle Helper": "पशुपालन सहायक",
    "House Help": "घरेलू सहायक",
    "Tailor": "टेलर",
    "Cook": "रसोइया",
    "Mobile Repair": "मोबाइल रिपेयर",
}

SEARCH_HINTS = ("need", "require", "looking for", "chahiye", "find")
LOCATION_PREFIXES = ("in", "at", "near", "from", "में", "mai", "main", "me")


@dataclass(slots=True)
class ParsedMessage:
    intent: str
    skill_slug: str | None = None
    skill_label: str | None = None
    location: str | None = None
    worker_name: str | None = None
    phone: str | None = None
    original_text: str | None = None


def normalize_text(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9\u0900-\u097f+\s,-]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def normalize_location(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[^a-z0-9\u0900-\u097f\s-]", " ", value.lower())
    return re.sub(r"\s+", " ", cleaned).strip() or None


def _find_skill(text: str) -> tuple[str | None, str | None]:
    best_skill: str | None = None
    best_score = 0
    for slug, aliases in SKILL_ALIASES.items():
        score = sum(1 for alias in aliases if alias in text)
        if score > best_score:
            best_skill = slug
            best_score = score

    if not best_skill:
        tokens = set(text.split())
        for slug, aliases in SKILL_ALIASES.items():
            alias_tokens = {token for alias in aliases for token in alias.split()}
            score = len(tokens & alias_tokens)
            if score > best_score:
                best_skill = slug
                best_score = score

    if not best_skill:
        return None, None
    return best_skill, SKILL_LABELS[best_skill]


def _extract_location(text: str) -> str | None:
    for prefix in LOCATION_PREFIXES:
        match = re.search(rf"\b{prefix}\s+([a-z0-9\u0900-\u097f][a-z0-9\u0900-\u097f\s-]+)$", text)
        if match:
            return normalize_location(match.group(1))
    return None


def _split_registration_payload(text: str) -> list[str]:
    text = text.replace("register", "", 1).replace("signup", "", 1).replace("join", "", 1)
    parts = [part.strip() for part in re.split(r"[,|]", text) if part.strip()]
    return parts


def parse_sms(message: str, sender_phone: str | None = None) -> ParsedMessage:
    normalized = normalize_text(message)
    if not normalized:
        return ParsedMessage(intent="unknown", original_text=message)

    if normalized.startswith(("register", "signup", "join")):
        fields = _split_registration_payload(normalized)
        name = fields[0].title() if fields else None
        skill_slug, skill_label = _find_skill(" ".join(fields[1:]))
        location = normalize_location(fields[2]) if len(fields) >= 3 else None
        phone = fields[3] if len(fields) >= 4 else sender_phone
        return ParsedMessage(
            intent="register",
            skill_slug=skill_slug,
            skill_label=skill_label,
            location=location,
            worker_name=name,
            phone=phone,
            original_text=message,
        )

    skill_slug, skill_label = _find_skill(normalized)
    location = _extract_location(normalized)
    if skill_slug or any(hint in normalized for hint in SEARCH_HINTS):
        return ParsedMessage(
            intent="search",
            skill_slug=skill_slug,
            skill_label=skill_label,
            location=location,
            phone=sender_phone,
            original_text=message,
        )

    return ParsedMessage(intent="unknown", original_text=message)


def resolve_skill(value: str) -> tuple[str | None, str | None]:
    return _find_skill(normalize_text(value))


def supported_skills() -> Iterable[str]:
    return SKILL_LABELS.values()


def skill_hindi_labels() -> dict[str, str]:
    return SKILL_HINDI_LABELS.copy()