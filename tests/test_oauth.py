import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.parse

from moco.core import SafeError
from moco.oauth import youtube_authorize


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.client = self.root / "desktop.json"
        self.client.write_text(json.dumps({"installed": {
            "client_id": "fixture-client", "client_secret": "fixture-secret"}}))
        self.auth = {}
        self.callbacks = [{"code": "fixture-code"}]
        self.responses = []
        self.closed = False
        test = self

        class Server:
            server_port = 12345

            def __init__(self, address, handler):
                test.assertEqual(address, ("127.0.0.1", 0))
                self.handler = handler

            def __enter__(self):
                return self

            def __exit__(self, *args):
                test.closed = True

            def handle_request(self):
                params = {"state": test.auth["state"][0], **test.callbacks.pop(0)}
                handler = object.__new__(self.handler)
                handler.path = "/callback?" + urllib.parse.urlencode(params)
                handler.send_response = test.responses.append
                handler.send_header = lambda *args: None
                handler.end_headers = lambda: None
                handler.wfile = io.BytesIO()
                handler.do_GET()

        def open_browser(url):
            parsed = urllib.parse.urlsplit(url)
            self.assertEqual((parsed.scheme, parsed.netloc), ("https", "accounts.google.com"))
            self.auth.update(urllib.parse.parse_qs(parsed.query))
            return True

        self.server = patch("moco.oauth.http.server.HTTPServer", Server).start()
        self.addCleanup(patch.stopall)
        patch("moco.oauth.webbrowser.open", side_effect=open_browser).start()
        self.http = patch("moco.oauth.HTTP").start().return_value
        self.http.json.return_value = {"refresh_token": "fixture-refresh", "scope": "fixture-scope"}
        self.secret = patch("moco.oauth.Secrets").start().return_value

    def test_authorization_can_finish_after_fourteen_minutes_with_pkce(self):
        with patch("moco.oauth.time.monotonic", side_effect=[100, 100 + 14 * 60]):
            result = youtube_authorize(self.client, self.root)
        self.assertEqual(result["status"], "stored_in_macos_keychain")
        self.assertTrue(self.closed)
        self.assertEqual(self.responses, [200])
        self.assertEqual(set(self.auth["scope"][0].split()), {
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly"})
        self.assertGreaterEqual(len(self.auth["state"][0]), 32)
        args, kwargs = self.http.json.call_args
        self.assertEqual(args, ("POST", "https://oauth2.googleapis.com/token"))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(
            kwargs["body"]["code_verifier"].encode()).digest()).decode().rstrip("=")
        self.assertEqual(self.auth["code_challenge"], [challenge])
        self.assertEqual(kwargs["body"]["redirect_uri"], "http://127.0.0.1:12345/callback")
        platform, stored = self.secret.set.call_args.args
        self.assertEqual(platform, "youtube")
        self.assertEqual(json.loads(stored)["refresh_token"], "fixture-refresh")
        self.assertNotIn("access_token", json.loads(stored))

    def test_wrong_state_cannot_complete_or_exchange_credentials(self):
        self.callbacks = [{"state": "wrong-state", "code": "wrong-code"}, {"code": "fixture-code"}]
        with patch("moco.oauth.time.monotonic", side_effect=[0, 10, 20]):
            youtube_authorize(self.client, self.root)
        self.assertEqual(self.responses, [400, 200])
        self.http.json.assert_called_once()
        self.assertEqual(self.http.json.call_args.kwargs["body"]["code"], "fixture-code")
        self.secret.set.assert_called_once()

    def test_expired_wait_is_not_reported_as_owner_denial(self):
        with patch("moco.oauth.time.monotonic", side_effect=[0, 3601]):
            with self.assertRaisesRegex(SafeError, "^oauth_authorization_timed_out$"):
                youtube_authorize(self.client, self.root)
        self.assertTrue(self.closed)
        self.http.json.assert_not_called()
        self.secret.set.assert_not_called()

    def test_explicit_owner_denial_does_not_store_credentials(self):
        self.callbacks = [{"error": "access_denied"}]
        with patch("moco.oauth.time.monotonic", side_effect=[0, 10]):
            with self.assertRaisesRegex(SafeError, "^oauth_authorization_denied$"):
                youtube_authorize(self.client, self.root)
        self.assertTrue(self.closed)
        self.http.json.assert_not_called()
        self.secret.set.assert_not_called()

    def test_missing_refresh_token_is_not_saved_as_connected(self):
        self.http.json.return_value = {"access_token": "fixture-access"}
        with patch("moco.oauth.time.monotonic", side_effect=[0, 10]):
            with self.assertRaisesRegex(SafeError, "^oauth_refresh_token_missing$"):
                youtube_authorize(self.client, self.root)
        self.secret.set.assert_not_called()
