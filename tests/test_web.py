from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient


class VillageJobPortalWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "web_jobs.db"
        os.environ["VILLAGE_JOB_PORTAL_DB"] = str(self.db_path)

        from village_job_portal.app import app

        self.client_manager = TestClient(app)
        self.client = self.client_manager.__enter__()

    def tearDown(self) -> None:
        self.client_manager.__exit__(None, None, None)
        os.environ.pop("VILLAGE_JOB_PORTAL_DB", None)
        self.temp_dir.cleanup()

    def test_home_page_loads(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("एक SMS में बुकिंग कीजिए", response.text)
        self.assertIn("WhatsApp Msg", response.text)

    def test_sms_api_returns_contacts(self) -> None:
        response = self.client.post(
            "/api/sms",
            json={
                "from_phone": "9876500000",
                "message": "Need Tractor Mechanic in Phulaut",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Top 2 Tractor Mechanic contacts", response.json()["reply"])

    def test_register_api_adds_worker(self) -> None:
        response = self.client.post(
            "/api/register",
            json={
                "name": "Asha Devi",
                "phone": "9991000001",
                "skill": "Plumber",
                "village": "Phulaut",
                "age": 33,
                "hourly_rate": 190,
                "daily_rate": 1300,
                "image_url": "https://example.com/asha.jpg",
                "availability_status": "working",
                "working_start_time": "09:00",
                "working_end_time": "18:00",
                "next_free_at": "आज 18:00 बजे",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Registered Asha Devi as Plumber", response.json()["reply"])
        self.assertEqual(response.json()["worker"]["age"], 33)
        self.assertEqual(response.json()["worker"]["daily_rate"], 1300)
        self.assertEqual(response.json()["worker"]["available"], 0)

    def test_worker_profile_page_loads(self) -> None:
        response = self.client.get("/workers/9000000001")

        self.assertEqual(response.status_code, 200)
        self.assertIn("पिछले 2 महीनों की गतिविधि", response.text)
        self.assertIn("Ramesh Yadav", response.text)
        self.assertIn("whatsapp://call?phone=9000000001", response.text)
        self.assertIn("https://wa.me/9000000001", response.text)

    def test_worker_profile_api_returns_history(self) -> None:
        response = self.client.get("/api/workers/9000000001")

        self.assertEqual(response.status_code, 200)
        self.assertIn("worker", response.json())
        self.assertGreaterEqual(response.json()["worker"]["last_two_month_jobs"], 1)

    def test_home_filter_query_is_applied(self) -> None:
        response = self.client.get("/?skill=Plumber&village=Phulaut&min_rating=4.0&max_hourly_rate=250")

        self.assertEqual(response.status_code, 200)
        self.assertIn('name="village" value="Phulaut"', response.text)
        self.assertIn("फ़िल्टर लागू करें", response.text)

    def test_register_form_supports_uploaded_image(self) -> None:
        response = self.client.post(
            "/register",
            data={
                "name": "Photo Worker",
                "phone": "9998000001",
                "skill": "Plumber",
                "village": "Phulaut",
                "age": "30",
                "hourly_rate": "180",
                "daily_rate": "1200",
                "image_url": "",
                "availability_status": "free",
                "working_start_time": "09:00",
                "working_end_time": "18:00",
                "next_free_at": "",
            },
            files={
                "profile_image": ("worker.jpg", b"fake-image-bytes", "image/jpeg"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("/static/uploads/", response.text)

    def test_signup_and_booking_updates_profile(self) -> None:
        signup_response = self.client.post(
            "/auth/signup",
            data={
                "full_name": "Booking User",
                "email": "booking.user@example.com",
                "phone": "8887776666",
                "password": "secure123",
                "next": "/",
            },
            follow_redirects=True,
        )
        self.assertEqual(signup_response.status_code, 200)

        book_response = self.client.post(
            "/book/9000000001",
            data={"notes": "कल सुबह 10 बजे आना"},
            follow_redirects=True,
        )
        self.assertEqual(book_response.status_code, 200)
        self.assertIn("बुकिंग कन्फर्म", book_response.text)
        self.assertIn("Booking User", book_response.text)

    def test_admin_dashboard_requires_admin_user(self) -> None:
        response = self.client.get("/admin/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 303)

    def test_google_signup_direct_without_details(self) -> None:
        response = self.client.post(
            "/auth/google-signup",
            data={"next": "/"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Google Demo User", response.text)

    def test_admin_login_and_dashboard(self) -> None:
        login_response = self.client.post(
            "/auth/login",
            data={
                "email": "admin@vjp.local",
                "password": "admin123",
                "next": "/admin/dashboard",
            },
            follow_redirects=True,
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("Recent Bookings", login_response.text)

    def test_admin_can_update_booking_progress(self) -> None:
        self.client.post(
            "/auth/signup",
            data={
                "full_name": "Progress User",
                "email": "progress.user@example.com",
                "phone": "7776665555",
                "password": "secure123",
                "next": "/",
            },
            follow_redirects=True,
        )
        self.client.post(
            "/book/9000000001",
            data={"notes": "काम ट्रैक करना है"},
            follow_redirects=True,
        )
        self.client.post("/auth/logout", follow_redirects=True)

        self.client.post(
            "/auth/login",
            data={
                "email": "admin@vjp.local",
                "password": "admin123",
                "next": "/admin/dashboard",
            },
            follow_redirects=True,
        )

        dashboard = self.client.get("/admin/dashboard")
        self.assertIn("काम कहाँ तक पहुँचा", dashboard.text)

        update_response = self.client.post(
            "/admin/bookings/1/progress",
            data={
                "status": "in_progress",
                "progress_percent": "65",
                "progress_note": "आधा प्लास्टर पूरा",
            },
            follow_redirects=True,
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertIn("65%", update_response.text)

        profile = self.client.get("/workers/9000000001")
        self.assertIn("65%", profile.text)
        self.assertIn("आधा प्लास्टर पूरा", profile.text)


if __name__ == "__main__":
    unittest.main()