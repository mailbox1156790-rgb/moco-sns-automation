import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import ssl
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from moco.accounts import AccountAPI, number
from moco.core import ROOT, SafeError, Store, UTC, make_draft, now, settings
from moco.engine import analysis, execute, render_with_retry, tick
from moco.github import GitHub, parse_command, poll
from moco.net import HTTP, NoRedirect
from scripts.configure_github import configure_operator


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.cfg = settings()
        self.cfg["production"] = {"platforms": ["threads", "instagram", "youtube"], "video_enabled": True}
        self.cfg["github"]["trusted_actor_ids"] = [123]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def post(self):
        row = self.store.add("youtube", make_draft("検証"))
        p = self.store.asset_dir(row["id"])
        for n in ["draft.json", "cover.png", "video.mp4"]:
            (p / n).write_bytes(b"fixture-test-only")
        (p / "draft.json").write_text(row["content"])
        return row

    def issue(self, action="status"):
        return {"id": 42, "number": 1, "state": "open", "user": {"id": 123}, "updated_at": now(),
                "labels": [{"name": "moco:command"}], "body": json.dumps({"version": 1, "command_id": "6e2e8a1b-e21e-453c-bd9b-b88bd217fb6e", "action": action})}


class StateTests(Base):
    def test_duplicate_draft_keeps_management_id(self):
        a, b = self.post(), self.post()
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(self.store.summary()), 1)

    def test_platforms_have_distinct_ids(self):
        a = self.post()
        b = self.store.add("threads", make_draft("検証"))
        self.assertNotEqual(a["id"], b["id"])

    def test_schedule_requires_approval_and_timezone(self):
        row = self.post()
        with self.assertRaises(SafeError):
            self.store.schedule(row["id"], "2099-01-01T10:00:00+09:00")
        self.store.approve(row["id"], self.store.bundle_digest(row["id"]))
        with self.assertRaises(SafeError):
            self.store.schedule(row["id"], "2099-01-01T10:00:00")

    def test_changed_media_invalidates_approval(self):
        row = self.post()
        self.store.approve(row["id"], self.store.bundle_digest(row["id"]))
        self.store.schedule(row["id"], "2099-01-01T10:00:00+09:00")
        self.store.db.execute("UPDATE posts SET scheduled_at='2000-01-01T00:00:00+00:00'")
        self.store.db.commit()
        (self.store.asset_dir(row["id"]) / "video.mp4").write_bytes(b"changed")
        tick(self.store, self.cfg)
        self.assertEqual(self.store.get(row["id"])["state"], "awaiting_review")

    def test_dry_schedule_never_marks_published(self):
        row = self.post()
        self.store.approve(row["id"], self.store.bundle_digest(row["id"]))
        self.store.db.execute("UPDATE posts SET state='scheduled',scheduled_at='2000-01-01T00:00:00+00:00'")
        self.store.db.commit()
        tick(self.store, self.cfg)
        final = self.store.get(row["id"])
        self.assertEqual(final["state"], "simulated")
        self.assertIsNone(final["remote_id"])
        self.assertIsNone(final["remote_url"])

    def test_stop_blocks_work_but_allows_status(self):
        self.store.stop()
        with self.assertRaises(SafeError):
            execute(self.store, self.cfg, {"action": "draft", "platform": "threads", "topic": "test"})
        self.assertTrue(execute(self.store, self.cfg, {"action": "status"})["stopped"])

    def test_process_lock(self):
        with self.store.lock():
            with self.assertRaises(SafeError):
                with self.store.lock():
                    pass

    def test_render_retries_are_bounded(self):
        row = self.post()
        with patch("moco.engine.render", side_effect=SafeError("local_media_tool_failed")):
            for _ in range(3):
                render_with_retry(self.store, self.cfg, row["id"])
        final = self.store.get(row["id"])
        self.assertEqual(final["attempts"], 3)
        self.assertIsNone(final["next_attempt"])

    def test_analysis_has_no_fabricated_data(self):
        result = analysis(self.store)
        self.assertEqual(result["measured_samples"], 0)
        data = json.loads((self.store.var / "reports/analysis.json").read_text())
        self.assertEqual(data["observations"], [])

    def test_id_path_traversal_rejected(self):
        with self.assertRaises(SafeError):
            self.store.asset_dir("../../secret")

    def test_restart_keeps_state(self):
        row = self.post()
        other = Store(self.root)
        self.assertEqual(other.get(row["id"])["state"], "awaiting_review")
        other.close()

    def test_revision_invalidates_old_render(self):
        row = self.post()
        self.store.approve(row["id"], self.store.bundle_digest(row["id"]))
        self.store.revise(row["id"], make_draft("別の企画"))
        self.assertIsNone(self.store.get(row["id"])["approved_digest"])
        with self.assertRaises(SafeError):
            self.store.bundle_digest(row["id"])

    def test_missing_media_invalidates_schedule(self):
        row = self.post()
        self.store.approve(row["id"], self.store.bundle_digest(row["id"]))
        self.store.db.execute("UPDATE posts SET state='scheduled',scheduled_at='2000-01-01T00:00:00+00:00'")
        self.store.db.commit()
        (self.store.asset_dir(row["id"]) / "video.mp4").unlink()
        tick(self.store, self.cfg)
        self.assertEqual(self.store.get(row["id"])["state"], "awaiting_review")


class CommandTests(Base):
    def test_trusted_command(self):
        self.assertEqual(parse_command(self.issue(), self.cfg["github"])["action"], "status")

    def test_untrusted_author(self):
        issue = self.issue(); issue["user"]["id"] = 999
        with self.assertRaises(SafeError):
            parse_command(issue, self.cfg["github"])

    def test_missing_label_and_old_issue(self):
        issue = self.issue(); issue["labels"] = []
        with self.assertRaises(SafeError):
            parse_command(issue, self.cfg["github"])
        issue = self.issue(); issue["updated_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaises(SafeError):
            parse_command(issue, self.cfg["github"])

    def test_remote_approval_resume_publish_shell_forbidden(self):
        for action in ["approve", "resume", "publish", "shell", "exec", "auth-youtube", "schedule"]:
            with self.assertRaises(SafeError):
                parse_command(self.issue(action), self.cfg["github"])

    def test_unknown_fields_rejected(self):
        issue = self.issue(); data = json.loads(issue["body"]); data["shell"] = "touch /tmp/pwned"; issue["body"] = json.dumps(data)
        with self.assertRaises(SafeError):
            parse_command(issue, self.cfg["github"])

    def test_editor_must_be_trusted(self):
        client = object.__new__(GitHub); client.cfg = self.cfg["github"]; client._token = "fixture"
        class FakeHTTP:
            def json(_, *args, **kwargs):
                return {"data": {"repository": {"issue": {"body": self.issue()["body"], "author": {"databaseId": 123}, "lastEditedAt": now(), "editor": {"databaseId": 999}}}}}
        client.http = FakeHTTP()
        with self.assertRaises(SafeError):
            client.verify_editor(self.issue())

    def test_command_replay_and_report_failure_do_not_repeat_execution(self):
        issues = [self.issue()]
        calls = []
        class FakeClient:
            fail_report = True
            def issues(_): return issues
            def verify_editor(_, issue): pass
            def report(_, *args):
                if _.fail_report: raise SafeError("http_network_or_tls_error")
                return 99
        client = FakeClient()
        with self.assertRaises(SafeError):
            poll(self.store, self.cfg, lambda c: calls.append(c) or {"ok": True}, client)
        client.fail_report = False
        poll(self.store, self.cfg, lambda c: calls.append(c), client)
        copied = copy.deepcopy(issues[0]); copied["id"] = 43; copied["number"] = 2; issues.append(copied)
        poll(self.store, self.cfg, lambda c: calls.append(c), client)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.db.execute("SELECT status FROM commands").fetchone()[0], "reported")


class HTTPTests(unittest.TestCase):
    def test_tls_verification_enabled(self):
        h = HTTP()
        self.assertEqual(h.context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(h.context.check_hostname)

    def test_http_and_unknown_host_and_token_in_url_rejected(self):
        h = HTTP()
        for url in ["http://api.github.com", "https://evil.invalid", "https://api.github.com/?access_token=fixture"]:
            with self.assertRaises(SafeError): h.json("GET", url)

    def test_redirect_is_blocked(self):
        with self.assertRaises(SafeError):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid")

    def test_missing_is_not_zero(self):
        self.assertIsNone(number(None))
        self.assertIsNone(number(True))
        self.assertEqual(number("0"), 0)

    def test_youtube_wrong_channel_rejected(self):
        cfg = settings()
        class Secret:
            def get(_, p): return json.dumps({"client_id": "fixture", "client_secret": "fixture", "refresh_token": "fixture"})
        class FakeHTTP:
            def json(_, method, url, *args, **kwargs):
                if method == "POST": return {"access_token": "fixture"}
                return {"items": [{"id": "mine" if "mine=true" in url else "target"}]}
        with self.assertRaises(SafeError):
            AccountAPI("youtube", cfg, Secret(), FakeHTTP()).identity()

    def test_post_failure_is_not_retried_or_leaked(self):
        h = HTTP()
        class Opener:
            calls = 0
            def open(_, *args, **kwargs):
                _.calls += 1
                raise urllib.error.HTTPError("https://api.github.com", 500, "fixture_secret_must_not_escape", {}, None)
        h.opener = Opener()
        with self.assertRaises(SafeError) as caught:
            h.json("POST", "https://api.github.com/user", token="fixture_secret_must_not_escape", body={})
        self.assertEqual(h.opener.calls, 1)
        self.assertEqual(str(caught.exception), "http_status_500")

    def test_youtube_zero_and_missing_metric_remain_distinct(self):
        cfg = settings(); cfg["accounts"]["youtube"].update(account_id="target", owner_confirmed=True)
        api = object.__new__(AccountAPI)
        api.platform, api.cfg, api.account = "youtube", cfg, cfg["accounts"]["youtube"]
        api.identity = lambda: {"account_id": "target"}
        api.get = lambda *args: {"items": [{"snippet": {"channelId": "target"}, "statistics": {"viewCount": "0"}}]}
        result = api.measured_metrics("fixture-video")
        self.assertEqual(result["metrics"]["views"], 0)
        self.assertIsNone(result["metrics"]["likes"])
        self.assertIn("likes", result["missing_metrics"])


class OperatorConfigurationTests(Base):
    def prepare(self, push=True):
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/settings.json", self.root / "config/settings.json")
        class Client:
            def identity(_):
                return {"repository": "mailbox1156790-rgb/moco-sns-automation", "login": "invited-operator", "id": 123, "push": push, "issues_enabled": True}
        return Client()

    def test_invited_collaborator_with_write_access_can_be_pinned(self):
        result = configure_operator(self.root, self.prepare())
        self.assertEqual(result["login"], "invited-operator")
        data = json.loads((self.root / "config/local.json").read_text())
        self.assertEqual(data["github"]["trusted_actor_ids"], [123])

    def test_read_only_operator_is_rejected(self):
        with self.assertRaises(SafeError):
            configure_operator(self.root, self.prepare(False))
        self.assertFalse((self.root / "config/local.json").exists())

    def test_runtime_symlink_and_existing_trust_are_preserved(self):
        client = self.prepare()
        shared = self.root / "runtime-local.json"
        shared.write_text(json.dumps({"github": {"trusted_actor_ids": [456]}}))
        local = self.root / "config/local.json"
        local.symlink_to(shared)
        configure_operator(self.root, client)
        self.assertTrue(local.is_symlink())
        self.assertEqual(json.loads(shared.read_text())["github"]["trusted_actor_ids"], [456, 123])


if __name__ == "__main__":
    unittest.main()
