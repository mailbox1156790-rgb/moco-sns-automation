import copy
import json
from pathlib import Path
import tempfile
import unittest

from moco.core import SafeError, Store, atomic_json, canonical, settings
from moco.reporting import public_measurements, report_metrics_checkpoint


class FakeGitHub:
    def __init__(self):
        self.issue = {"id": 123, "state": "open", "user": {"id": 456}}
        self.remote_comments = []
        self.posts = 0
        self.lose_response = False
        self.save_comment = True

    def call(self, method, path, body=None):
        if method == "GET":
            return copy.deepcopy(self.issue)
        self.posts += 1
        comment = {"id": 1000 + self.posts, "body": body["body"], "user": {"id": 456}}
        if self.save_comment:
            self.remote_comments.append(comment)
        if self.lose_response:
            raise SafeError("network_request_failed")
        return comment

    def comments(self, number):
        return copy.deepcopy(self.remote_comments)


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))
        self.addCleanup(self.store.close)
        self.cfg = settings()
        self.cfg["github"].update(trusted_actor_ids=[456], metrics_report_issue={"number": 3, "id": 123})
        self.cfg["accounts"]["youtube"].update(owner_confirmed=True, account_id="fixture-channel")
        self.client = FakeGitHub()
        self.batch("2026-10-19T00:00:00+00:00")
        self.measurement = {"platform": "youtube", "account_id": "fixture-channel",
            "remote_id": "abcdefghijk", "remote_url": "https://www.youtube.com/shorts/abcdefghijk",
            "source": "youtube_data_api.videos.list", "visibility": "public",
            "collected_at": "2026-10-19T00:00:01+00:00",
            "metrics": {"views": 0, "likes": None, "comments": 2, "private_insight": 999},
            "unexpected_credential": "fixture-secret-must-not-appear"}
        self.save(self.measurement)

    def batch(self, at):
        atomic_json(self.store.var / "reports/metrics-collection.json", {
            "status": "completed", "last_attempt_at": at, "finished_at": at,
            "updated_posts": 1, "failures": [], "next_due_at": "2026-10-20T00:00:00+00:00"})

    def save(self, data, post_id="fixture-post"):
        self.store.db.execute("INSERT INTO metrics(post_id,source,collected_at,payload) VALUES(?,?,?,?)",
            (post_id, data["source"], data["collected_at"], canonical(data)))
        self.store.db.commit()

    def report(self, store=None):
        return report_metrics_checkpoint(store or self.store, self.cfg, self.client)

    def test_only_public_counters_are_shared_and_missing_is_not_zero(self):
        self.assertEqual(self.report()["status"], "reported")
        body = self.client.remote_comments[0]["body"]
        self.assertNotIn("fixture-secret", body)
        self.assertNotIn("private_insight", body)
        payload = json.loads(body.split("```json\n")[1].split("\n```")[0])
        self.assertEqual(payload["sns_posts_created"], 0)
        self.assertEqual(payload["latest_public_youtube_measurements"][0]["metrics"],
            {"views": 0, "likes": None, "comments": 2})

    def test_latest_private_or_unverified_measurement_is_never_reported(self):
        for change in ({"visibility": "private"}, {"visibility": "unlisted"},
                {"account_id": "another-channel"}, {"platform": "instagram"},
                {"remote_url": "https://example.test/secret"}, {"source": "estimated"},
                {"metrics": {"views": True}}, {"remote_id": "bad\nidentifier"}):
            with self.subTest(change=change):
                self.save(dict(self.measurement, **change))
                self.assertEqual(public_measurements(self.store, self.cfg), [])
        self.save(self.measurement)
        self.cfg["accounts"]["youtube"]["owner_confirmed"] = False
        self.assertEqual(public_measurements(self.store, self.cfg), [])

    def test_report_survives_restart_without_duplicate_post(self):
        self.report()
        other = Store(self.store.root)
        try:
            self.assertEqual(self.report(other)["status"], "reported")
        finally:
            other.close()
        self.assertEqual(self.client.posts, 1)

    def test_lost_post_response_is_reconciled_by_reading_remote_comments(self):
        self.client.lose_response = True
        self.assertEqual(self.report()["status"], "failed")
        self.assertEqual(self.report()["status"], "reported")
        self.assertEqual(self.client.posts, 1)

    def test_unknown_post_is_not_retried_and_original_outbox_is_preserved(self):
        self.client.lose_response = True
        self.client.save_comment = False
        self.report()
        self.batch("2026-10-19T06:00:00+00:00")
        self.assertEqual(self.report()["status"], "verification_required")
        outbox = json.loads((self.store.var / "reports/github-metrics-outbox.json").read_text())
        self.assertEqual(outbox["run_key"], "2026-10-19T00:00:00+00:00")
        self.assertEqual(self.client.posts, 1)

    def test_untrusted_or_changed_destination_cannot_receive_report(self):
        for issue in ({"id": 999}, {"user": {"id": 999}}, {"state": "closed"}, {"pull_request": {}}):
            with self.subTest(issue=issue):
                self.client.issue = dict({"id": 123, "state": "open", "user": {"id": 456}}, **issue)
                self.assertEqual(self.report()["error_code"], "metrics_report_destination_not_trusted")
        self.assertEqual(self.client.posts, 0)
        self.cfg["github"]["metrics_report_issue"] = {"number": 4, "id": 999}
        self.assertEqual(self.report()["error_code"], "metrics_report_destination_changed")

    def test_disabled_stopped_and_incomplete_collection_do_not_post(self):
        del self.cfg["github"]["metrics_report_issue"]
        self.assertEqual(self.report()["status"], "disabled")
        self.cfg["github"]["metrics_report_issue"] = {"number": 3, "id": 123}
        atomic_json(self.store.var / "reports/metrics-collection.json", {"status": "collecting"})
        self.assertEqual(self.report()["status"], "waiting_for_collection")
        self.store.stop()
        self.assertEqual(self.report()["status"], "stopped")
        self.assertEqual(self.client.posts, 0)

    def test_next_completed_batch_produces_one_new_report(self):
        self.report()
        self.batch("2026-10-19T06:00:00+00:00")
        self.report()
        self.report()
        self.assertEqual(self.client.posts, 2)
        self.assertEqual(len(self.client.remote_comments), 2)
