from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from village_job_portal.service import VillageJobPortalService


class VillageJobPortalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "village_jobs.db"
        self.service = VillageJobPortalService(self.db_path)
        self.service.initialize(seed=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_search_returns_ranked_workers(self) -> None:
        response = self.service.process_message("9990000000", "Need Tractor Mechanic in Phulaut")

        self.assertIn("Top 2 Tractor Mechanic contacts", response)
        self.assertIn("Ramesh Yadav - 9000000001", response)
        self.assertIn("Sohan Lal - 9000000003", response)

    def test_registration_via_sms_persists_worker(self) -> None:
        response = self.service.process_message(
            "9990000001",
            "REGISTER, Sita Devi, Plumber, Phulaut, 9990000001",
        )

        self.assertIn("Registered Sita Devi as Plumber in Phulaut", response)

        search_response = self.service.process_message("9990000000", "Need plumber in Phulaut")
        self.assertIn("Sita Devi - 9990000001", search_response)

    def test_unknown_skill_returns_guidance(self) -> None:
        response = self.service.process_message("9990000000", "Need drone pilot in Phulaut")

        self.assertIn("Skill not recognized", response)

    def test_worker_profile_includes_recent_history_and_rates(self) -> None:
        profile = self.service.get_worker_profile("9000000001")

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile["age"], 34)
        self.assertEqual(profile["hourly_rate"], 220.0)
        self.assertGreaterEqual(profile["last_two_month_jobs"], 1)
        self.assertIn("recent_history", profile)
        self.assertIn("status_symbol", profile)
        self.assertIn("working_time_label", profile)


if __name__ == "__main__":
    unittest.main()