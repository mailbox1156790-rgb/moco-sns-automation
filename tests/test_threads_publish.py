import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from moco.core import SafeError, Store, make_draft, settings
from moco.engine import analysis, execute, tick
from moco.media import render
from moco.threads_publish import approve_threads, publish_threads


class ThreadsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))
        self.addCleanup(self.store.close)
        self.cfg = settings()
        self.cfg.update(mode="threads_text", production={"platforms": ["threads"], "video_enabled": False})
        self.cfg["metrics_collection"]["enabled"] = False
        self.cfg["accounts"]["threads"].update(account_id="123", owner_confirmed=True, profile_url="https://www.threads.com/@fixture_owner")
        self.cfg["publishing"] = {"threads": {"enabled": True, "permission_owner_approved": True, "automatic_scheduling": False}}
        self.cfg["github"].pop("metrics_report_issue", None)
        content = make_draft("下書きから始める")
        content["caption"] = "AIで下書きを1つ。\n確認してから公開しよう。"
        self.row = self.store.add("threads", content)
        render(self.store, self.row["id"], self.cfg)
        self.digest = self.store.bundle_digest(self.row["id"])
        self.calls = []
        test = self

        class Client:
            status = "FINISHED"
            create_error = False
            publish_error = False
            verify_error = False
            account_id = "123"

            def identity(self):
                return {"account_id": self.account_id, "username": "fixture_owner"}

            def create(self, text):
                test.calls.append("create")
                if self.create_error:
                    raise SafeError("http_network_or_tls_error")
                return {"id": "456"}

            def publish(self, container):
                test.calls.append("publish")
                if self.publish_error:
                    raise SafeError("http_network_or_tls_error")
                return {"id": "789"}

            def get(self, path, params):
                if path == "/456":
                    return {"status": self.status}
                if path == "/789":
                    if self.verify_error:
                        raise SafeError("http_status_500")
                    return {"id": "789", "username": "fixture_owner", "text": content["caption"],
                            "media_type": "TEXT_POST", "permalink": "https://www.threads.com/@fixture_owner/post/example"}
                if path == "/123/threads":
                    return {"data": [{"id": "789", "permalink": "https://www.threads.com/@fixture_owner/post/example"}]}
                raise AssertionError("unanticipated_fixture_request")
        self.client = Client()

    def approve(self, when="now"):
        return approve_threads(self.store, self.cfg, self.row["id"], self.digest, when)

    def publish(self):
        return publish_threads(self.store, self.cfg, self.row["id"], self.client)

    def test_threads_text_needs_no_video_tool_and_tamper_invalidates_digest(self):
        with patch("moco.media.run", side_effect=AssertionError("video_tool_must_not_run")):
            render(self.store, self.row["id"], self.cfg)
        path = self.store.asset_dir(self.row["id"]) / "post.txt"
        path.write_text("changed")
        with self.assertRaises(SafeError):
            self.store.bundle_digest(self.row["id"])

    def test_paused_video_creation_render_and_retries_cannot_run(self):
        with self.assertRaisesRegex(SafeError, "production_paused_by_owner"):
            execute(self.store, self.cfg, {"action": "draft", "platform": "youtube", "topic": "test"})
        row = self.store.add("instagram", make_draft("old"))
        with self.assertRaisesRegex(SafeError, "production_paused_by_owner"):
            render(self.store, row["id"], self.cfg)
        self.store.db.execute("UPDATE posts SET state='failed',attempts=1,next_attempt='2000-01-01T00:00:00+00:00' WHERE id=?", (row["id"],))
        self.store.db.commit()
        with patch("moco.engine.render", side_effect=AssertionError("paused_retry_must_not_render")):
            tick(self.store, self.cfg)

    def test_unapproved_post_and_disabled_permission_never_send(self):
        with self.assertRaises(SafeError): self.publish()
        self.approve()
        self.cfg["publishing"]["threads"]["permission_owner_approved"] = False
        with self.assertRaises(SafeError): self.publish()
        self.assertEqual(self.calls, [])

    def test_draft_mode_never_sends_even_if_enabled(self):
        self.approve()
        self.cfg["mode"] = "draft_only"
        with self.assertRaises(SafeError): self.publish()
        self.assertEqual(self.calls, [])

    def test_wrong_numeric_owner_never_sends(self):
        self.approve()
        self.client.account_id = "999"
        with self.assertRaises(SafeError): self.publish()
        self.assertEqual(self.calls, [])

    def test_profile_target_mismatch_never_sends(self):
        self.approve()
        self.cfg["accounts"]["threads"]["profile_url"] = "https://www.threads.com/@another_owner"
        with self.assertRaises(SafeError): self.publish()
        self.assertEqual(self.calls, [])

    def test_content_change_after_approval_cannot_send(self):
        self.approve()
        content = make_draft("revised")
        self.store.revise(self.row["id"], content)
        render(self.store, self.row["id"], self.cfg)
        with self.assertRaises(SafeError): self.publish()
        self.assertEqual(self.calls, [])

    def test_future_approved_time_is_respected(self):
        self.approve("2099-01-01T00:00:00+09:00")
        self.assertEqual(self.publish()["state"], "waiting_for_approved_time")
        self.assertEqual(self.calls, [])

    def test_known_success_verifies_id_url_body_owner_and_does_not_duplicate(self):
        self.approve()
        outcome = self.publish()
        self.assertEqual(outcome["state"], "published")
        self.assertEqual(outcome["remote_id"], "789")
        self.assertTrue(outcome["remote_url"].startswith("https://www.threads.com/@fixture_owner/"))
        self.publish()
        self.assertEqual(self.calls, ["create", "publish"])

    def test_unknown_publish_response_never_replays_or_allows_revision(self):
        self.approve()
        self.client.publish_error = True
        self.assertEqual(self.publish()["state"], "reconciliation_required")
        self.publish()
        self.assertEqual(self.calls, ["create", "publish"])
        with self.assertRaises(SafeError): self.store.revise(self.row["id"], make_draft("new"))

    def test_unknown_create_response_never_replays(self):
        self.approve()
        self.client.create_error = True
        self.assertEqual(self.publish()["state"], "reconciliation_required")
        self.publish()
        self.assertEqual(self.calls, ["create"])

    def test_in_progress_container_reuses_known_container(self):
        self.approve()
        self.client.status = "IN_PROGRESS"
        self.assertEqual(self.publish()["state"], "waiting_for_container")
        self.client.status = "FINISHED"
        self.assertEqual(self.publish()["state"], "published")
        self.assertEqual(self.calls, ["create", "publish"])

    def test_verification_failure_only_retries_get(self):
        self.approve()
        self.client.verify_error = True
        self.assertEqual(self.publish()["state"], "verification_required")
        self.assertEqual(self.store.get(self.row["id"])["remote_id"], "789")
        # A crash can occur after the delivery journal commits its ID and before
        # the main post row receives it. Reconciliation must repair that row.
        self.store.db.execute("UPDATE posts SET remote_id=NULL WHERE id=?", (self.row["id"],))
        self.store.db.commit()
        self.client.verify_error = False
        self.assertEqual(self.publish()["state"], "published")
        self.assertEqual(self.store.get(self.row["id"])["remote_id"], "789")
        self.assertEqual(self.calls, ["create", "publish"])

    def test_stop_after_creation_prevents_publication(self):
        self.approve()
        original = self.client.create
        def create(text):
            result = original(text)
            self.store.stop()
            return result
        self.client.create = create
        with self.assertRaises(SafeError): self.publish()
        self.assertEqual(self.calls, ["create"])

    def test_same_text_in_different_draft_is_deduplicated(self):
        self.approve()
        content = json.loads(self.row["content"])
        content["title"] = "same body, different title"
        other = self.store.add("threads", content)
        render(self.store, other["id"], self.cfg)
        with self.assertRaisesRegex(SafeError, "threads_duplicate_text_delivery_blocked"):
            approve_threads(self.store, self.cfg, other["id"], self.store.bundle_digest(other["id"]), "now")

    def test_worker_auto_publication_is_off_until_explicitly_enabled(self):
        self.approve()
        with patch("moco.threads_publish.ThreadsWriteAPI", side_effect=AssertionError("must_not_connect")):
            self.assertFalse(tick(self.store, self.cfg)["public"])
        self.assertEqual(self.calls, [])

    def test_worker_approved_schedule_can_publish_only_threads(self):
        self.approve()
        self.cfg["publishing"]["threads"]["automatic_scheduling"] = True
        with patch("moco.threads_publish.ThreadsWriteAPI", return_value=self.client):
            outcome = tick(self.store, self.cfg)
        self.assertTrue(outcome["public"])
        self.assertEqual(self.calls, ["create", "publish"])

    def test_verification_requires_exact_body_and_owned_permalink(self):
        self.approve()
        original = self.client.get
        def get(path, params):
            data = original(path, params)
            if path == "/789": data["text"] = "not the approved content"
            return data
        self.client.get = get
        self.assertEqual(self.publish()["state"], "verification_required")
        self.assertIsNone(self.store.get(self.row["id"])["remote_url"])

    def test_active_analysis_excludes_preserved_other_platform_measurements(self):
        for platform in ["threads", "youtube"]:
            self.store.db.execute("INSERT INTO metrics(post_id,source,collected_at,payload) VALUES(?,?,?,?)",
                (platform + "_fixture", "fixture", "2026-10-19T00:00:00+00:00", json.dumps({"platform": platform, "metrics": {"views": 0}})))
        self.store.db.commit()
        self.assertEqual(analysis(self.store, ["threads"])["measured_samples"], 1)
        report = json.loads((self.store.var / "reports/analysis.json").read_text())
        self.assertEqual([m["platform"] for m in report["observations"]], ["threads"])
