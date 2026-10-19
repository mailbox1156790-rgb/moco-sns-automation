import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from moco.collection import refresh_metrics, save_owned_measurement
from moco.core import SafeError, Store, settings


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))
        self.addCleanup(self.store.close)
        self.cfg = settings()
        self.cfg["metrics_collection"] = {"enabled": True, "platforms": ["youtube"],
            "interval_seconds": 21600, "max_posts_per_run": 20}
        self.cfg["accounts"]["youtube"].update(owner_confirmed=True, account_id="fixture-channel")
        self.row = self.store.add("youtube", {"existing_remote_id": "fixture-video"})
        self.store.db.execute("UPDATE posts SET state='published',remote_id='fixture-video',remote_url='https://www.youtube.com/shorts/fixture-video' WHERE id=?", (self.row["id"],))
        self.store.db.commit()
        self.calls = []
        test = self

        class Client:
            def measured_metrics(self, remote_id):
                test.calls.append(remote_id)
                return {"platform": "youtube", "remote_id": remote_id, "account_id": "fixture-channel",
                    "source": "fixture", "collected_at": "2026-10-19T00:00:00+00:00",
                    "metrics": {"views": 0, "likes": None}}
        self.factory = lambda *args: Client()

    def run_job(self, at="2026-10-19T00:00:00+00:00", **kwargs):
        with patch("moco.collection.now", return_value=at):
            return refresh_metrics(self.store, self.cfg, kwargs.get("factory", self.factory))

    def test_actual_zero_and_missing_are_preserved_without_creating_posts(self):
        result = self.run_job()
        payload = json.loads(self.store.db.execute("SELECT payload FROM metrics").fetchone()[0])
        self.assertEqual(payload["metrics"], {"views": 0, "likes": None})
        self.assertEqual(result["updated_posts"], 1)
        self.assertEqual(len(self.store.summary()), 1)
        self.assertEqual(self.store.get(self.row["id"])["remote_id"], "fixture-video")

    def test_interval_survives_restart_and_allows_next_due_run(self):
        self.run_job()
        other = Store(self.store.root)
        try:
            with patch("moco.collection.now", return_value="2026-10-19T00:02:00+00:00"):
                result = refresh_metrics(other, self.cfg, self.factory)
            self.assertEqual(result["status"], "waiting")
            self.assertEqual(len(self.calls), 1)
        finally:
            other.close()
        self.run_job("2026-10-19T06:00:00+00:00")
        self.assertEqual(len(self.calls), 2)

    def test_disabled_and_stopped_do_not_read_accounts(self):
        self.cfg["metrics_collection"]["enabled"] = False
        self.assertEqual(self.run_job()["status"], "disabled")
        self.cfg["metrics_collection"]["enabled"] = True
        self.store.stop()
        self.assertEqual(self.run_job()["status"], "stopped")
        self.assertEqual(self.calls, [])

    def test_unverified_owner_is_not_collected(self):
        self.cfg["accounts"]["youtube"]["owner_confirmed"] = False
        result = self.run_job()
        self.assertEqual(result["failures"][0]["error_code"], "owner_confirmed_pinned_account_required")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM metrics").fetchone()[0], 0)

    def test_wrong_remote_identity_cannot_be_saved(self):
        def factory(*args):
            client = self.factory()
            original = client.measured_metrics
            client.measured_metrics = lambda r: dict(original(r), account_id="another-channel")
            return client
        result = self.run_job(factory=factory)
        self.assertEqual(result["failures"][0]["error_code"], "collected_measurement_identity_mismatch")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM metrics").fetchone()[0], 0)

    def test_invalid_interval_fails_before_network_access(self):
        self.cfg["metrics_collection"]["interval_seconds"] = 1
        with self.assertRaisesRegex(SafeError, "metrics_collection_settings_invalid"):
            self.run_job()
        self.assertEqual(self.calls, [])

    def test_failed_read_does_not_create_zero_metrics_or_retry_each_tick(self):
        def factory(*args):
            raise SafeError("keychain_credential_unavailable")
        result = self.run_job(factory=factory)
        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["updated_posts"], 0)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM metrics").fetchone()[0], 0)
        self.assertEqual(self.run_job("2026-10-19T00:02:00+00:00")["status"], "waiting")

    def test_manual_collection_reuses_an_already_verified_created_post(self):
        measurement = {"remote_url": "https://www.youtube.com/shorts/fixture-video", "source": "fixture",
                       "collected_at": "2026-10-19T00:00:00+00:00", "metrics": {"views": 0}}
        post_id = save_owned_measurement(self.store, "youtube", "fixture-video", measurement)
        self.assertEqual(post_id, self.row["id"])
        self.assertEqual(len(self.store.summary()), 1)

    def test_collection_cannot_bypass_new_publication_body_and_url_verification(self):
        self.store.db.execute("UPDATE posts SET state='verification_required' WHERE id=?", (self.row["id"],))
        self.store.db.commit()
        with self.assertRaisesRegex(SafeError, "remote_post_publication_must_be_reconciled_first"):
            save_owned_measurement(self.store, "youtube", "fixture-video", {})
        self.assertEqual(self.store.get(self.row["id"])["state"], "verification_required")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM metrics").fetchone()[0], 0)
