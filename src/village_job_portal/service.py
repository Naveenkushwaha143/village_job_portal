from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from .db import WorkerDirectory, WorkerRecord
from .parser import parse_sms, normalize_location, resolve_skill, skill_hindi_labels, supported_skills


class VillageJobPortalService:
    def __init__(self, db_path: str | Path = "data/village_jobs.db"):
        self.directory = WorkerDirectory(db_path)

    def initialize(self, seed: bool = False) -> None:
        self.directory.initialize(seed=seed)

    def register_worker(
        self,
        name: str,
        phone: str,
        skill: str,
        location: str,
        age: int = 28,
        hourly_rate: float = 120.0,
        daily_rate: float = 850.0,
        image_url: str = "",
        available: int = 1,
        working_start_time: str = "09:00",
        working_end_time: str = "18:00",
        next_free_at: str = "",
    ) -> WorkerRecord:
        skill_slug, skill_label = resolve_skill(skill)
        if not skill_slug or not skill_label:
            raise ValueError("Skill not recognized")

        village_tag = normalize_location(location)
        if not village_tag:
            raise ValueError("Location is required")

        record = WorkerRecord(
            name=name,
            phone=phone,
            skill_slug=skill_slug,
            skill_label=skill_label,
            village=village_tag.title(),
            village_tag=village_tag,
            location_tag=village_tag,
            age=age,
            image_url=image_url.strip(),
            hourly_rate=hourly_rate,
            daily_rate=daily_rate,
            available=available,
            working_start_time=working_start_time.strip() or "09:00",
            working_end_time=working_end_time.strip() or "18:00",
            next_free_at=(next_free_at.strip() or ("अभी उपलब्ध" if available == 1 else (working_end_time.strip() or "18:00"))),
        )
        self.directory.register_worker(record)
        return record

    def search_directory(self, skill_slug: str, location: str | None = None, limit: int = 3) -> list[dict[str, object]]:
        matches = self.directory.search_workers(skill_slug, normalize_location(location), limit=limit)
        return [dict(match) for match in matches]

    def supported_skills(self) -> list[str]:
        return sorted(supported_skills())

    def skill_hindi_labels(self) -> dict[str, str]:
        return skill_hindi_labels()

    def create_user(self, full_name: str, email: str, phone: str, password_hash: str, provider: str = "local") -> int:
        return self.directory.create_user(full_name, email, phone, password_hash, provider)

    def get_user_by_email(self, email: str) -> dict[str, object] | None:
        user = self.directory.get_user_by_email(email)
        return dict(user) if user else None

    def get_user_by_id(self, user_id: int) -> dict[str, object] | None:
        user = self.directory.get_user_by_id(user_id)
        return dict(user) if user else None

    def create_session(self, user_id: int, hours_valid: int = 24) -> str:
        return self.directory.create_session(user_id, hours_valid)

    def get_user_by_session_token(self, token: str) -> dict[str, object] | None:
        user = self.directory.get_user_by_session_token(token)
        return dict(user) if user else None

    def delete_session(self, token: str) -> None:
        self.directory.delete_session(token)

    def create_booking(self, worker_phone: str, booked_by_user_id: int, notes: str = "") -> int:
        booking_id = self.directory.create_booking(worker_phone, booked_by_user_id, notes)
        user = self.directory.get_user_by_id(booked_by_user_id)
        if user:
            user_name = str(user["full_name"])
            self.directory.set_worker_booking_status(
                worker_phone,
                is_free=False,
                next_free_at=f"बुक्ड by {user_name}",
            )
        return booking_id

    def update_booking_progress(self, booking_id: int, progress_percent: int, progress_note: str, status: str) -> None:
        self.directory.update_booking_progress(booking_id, progress_percent, progress_note, status)
        booking = self.directory.get_booking_by_id(booking_id)
        if not booking:
            return

        booking_status = str(booking["status"])
        is_completed = booking_status == "completed"
        worker_phone = str(booking["worker_phone"])
        if is_completed:
            self.directory.set_worker_booking_status(worker_phone, is_free=True, next_free_at="अभी उपलब्ध")
        else:
            progress = int(booking["progress_percent"])
            self.directory.set_worker_booking_status(
                worker_phone,
                is_free=False,
                next_free_at=f"काम {progress}% पूरा",
            )

    def list_recent_bookings(self, limit: int = 50) -> list[dict[str, object]]:
        return [dict(row) for row in self.directory.list_recent_bookings(limit=limit)]

    def list_workers(
        self,
        limit: int | None = None,
        skill: str | None = None,
        village: str | None = None,
        min_rating: float | None = None,
        max_hourly_rate: float | None = None,
    ) -> list[dict[str, object]]:
        workers = [self._decorate_worker(dict(row)) for row in self.directory.list_workers(limit=None)]

        if skill:
            skill_value = skill.strip().lower()
            workers = [worker for worker in workers if str(worker.get("skill_label", "")).lower() == skill_value]

        if village:
            village_value = village.strip().lower()
            workers = [worker for worker in workers if village_value in str(worker.get("village", "")).lower()]

        if min_rating is not None:
            workers = [worker for worker in workers if float(worker.get("rating", 0.0)) >= min_rating]

        if max_hourly_rate is not None:
            workers = [worker for worker in workers if float(worker.get("hourly_rate", 0.0)) <= max_hourly_rate]

        if limit is not None:
            workers = workers[:limit]

        return workers

    def get_worker_profile(self, phone: str) -> dict[str, object] | None:
        worker = self.directory.get_worker_profile(phone)
        if worker is None:
            return None

        profile = self._decorate_worker(dict(worker))
        history = [dict(row) for row in self.directory.get_recent_work_history(int(worker["id"]))]
        total_earnings = sum(float(item["total_earned"]) for item in history)
        total_hours = sum(float(item["hours_worked"]) for item in history)
        profile["recent_history"] = history
        profile["last_two_month_jobs"] = len(history)
        profile["last_two_month_earnings"] = total_earnings
        profile["last_two_month_hours"] = total_hours
        return profile

    def _decorate_worker(self, worker: dict[str, object]) -> dict[str, object]:
        name = str(worker.get("name", ""))
        initials = "".join(part[0] for part in name.split()[:2]).upper() or "WK"
        worker["initials"] = initials
        worker["image_url"] = str(worker.get("image_url", "") or "")

        raw_phone = str(worker.get("phone", ""))
        phone_digits = "".join(ch for ch in raw_phone if ch.isdigit())
        worker["phone_digits"] = phone_digits

        whatsapp_text = quote_plus(
            f"Namaste {name} ji, mujhe aapki {worker.get('skill_label', 'service')} booking chahiye."
        )
        sms_text = quote_plus(
            f"Namaste {name} ji, mujhe aapki {worker.get('skill_label', 'service')} booking chahiye."
        )
        worker["call_url"] = f"tel:{raw_phone}" if raw_phone else ""
        worker["whatsapp_message_url"] = (
            f"https://wa.me/{phone_digits}?text={whatsapp_text}" if phone_digits else ""
        )
        worker["whatsapp_call_url"] = (
            f"whatsapp://call?phone={phone_digits}" if phone_digits else ""
        )
        worker["sms_message_url"] = (
            f"sms:{raw_phone}?body={sms_text}" if raw_phone else ""
        )

        is_free = int(worker.get("available", 0)) == 1
        worker["status_symbol"] = "🟢" if is_free else "🔴"
        worker["status_label"] = "Free" if is_free else "Working"
        worker["status_text_hi"] = "फ्री" if is_free else "काम पर"
        worker["working_time_label"] = (
            f"{worker.get('working_start_time', '09:00')} - {worker.get('working_end_time', '18:00')}"
        )
        worker["next_free_display"] = str(worker.get("next_free_at", "") or "अभी उपलब्ध")

        latest_booking = self.directory.get_latest_booking_for_worker(raw_phone) if raw_phone else None
        if latest_booking:
            booking = dict(latest_booking)
            worker["booking_info"] = {
                "booked_by_name": booking.get("booked_by_name", ""),
                "booked_by_phone": booking.get("booked_by_phone", ""),
                "created_at": booking.get("created_at", ""),
                "notes": booking.get("notes", ""),
                "status": booking.get("status", "booked"),
                "progress_percent": booking.get("progress_percent", 0),
                "progress_note": booking.get("progress_note", ""),
                "updated_at": booking.get("updated_at", ""),
            }
        else:
            worker["booking_info"] = None
        return worker

    def process_message(self, sender_phone: str, message: str) -> str:
        parsed = parse_sms(message, sender_phone=sender_phone)

        if parsed.intent == "register":
            if not parsed.worker_name or not parsed.skill_slug or not parsed.skill_label or not parsed.location:
                return (
                    "Registration format: REGISTER, Name, Skill, Village, Phone. "
                    "Example: REGISTER, Ramesh, Tractor Mechanic, Rampur, 9876543210"
                )

            record = self.register_worker(
                name=parsed.worker_name,
                phone=parsed.phone or sender_phone,
                skill=parsed.skill_label,
                location=parsed.location,
            )
            return (
                f"Registered {record.name} as {record.skill_label} in {record.village}. "
                f"Contact saved: {record.phone}."
            )

        if parsed.intent == "search":
            if not parsed.skill_slug:
                return (
                    "Skill not recognized. Supported skills: "
                    + ", ".join(sorted(supported_skills()))
                )

            matches = self.search_directory(parsed.skill_slug, parsed.location)
            if not matches:
                label = parsed.skill_label or "worker"
                if parsed.location:
                    return f"No available {label} found in {parsed.location.title()} right now."
                return f"No available {label} found right now."

            lines = [f"Top {len(matches)} {matches[0]['skill_label']} contacts:"]
            for index, match in enumerate(matches, start=1):
                lines.append(
                    f"{index}. {match['name']} - {match['phone']} ({match['village']}, rating {match['rating']:.1f})"
                )
            return " ".join(lines)

        return (
            "Send SEARCH like 'Need Tractor Mechanic in Rampur' or REGISTER like "
            "'REGISTER, Ramesh, Tractor Mechanic, Rampur, 9876543210'."
        )