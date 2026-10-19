import unittest
import urllib.parse

from moco.core import SafeError
from moco.token_import import TokenIntake


class TokenImportTests(unittest.TestCase):
    def setUp(self):
        self.writes = []
        self.intake = TokenIntake("instagram", lambda p, v: self.writes.append((p, v)))
        self.origin = "http://127.0.0.1:12345"
        self.headers = {"Host": "127.0.0.1:12345", "Origin": self.origin,
            "Content-Type": "application/x-www-form-urlencoded"}
        self.token = "fixture-read-token-for-tests-only"

    def body(self, **kwargs):
        return urllib.parse.urlencode(dict(csrf=self.intake.csrf, token=self.token, **kwargs)).encode()

    def test_valid_token_goes_to_writer_without_returning_secret(self):
        result = self.intake.accept(self.headers, self.body(), self.origin)
        self.assertEqual(self.writes, [("instagram", self.token)])
        self.assertEqual(result["status"], "stored_in_macos_keychain")
        self.assertFalse(result["replaced_existing"])
        self.assertFalse(result["api_identity_verified"])
        self.assertNotIn(self.token, str(result))
        self.assertNotIn(self.token, self.intake.page())

    def test_cross_origin_and_changed_host_cannot_store_credentials(self):
        for change in ({"Origin": "https://example.test"}, {"Origin": "null"},
                {"Host": "example.test"}, {"Content-Type": "text/plain"}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(SafeError, "token_import_request_rejected"):
                    self.intake.accept(dict(self.headers, **change), self.body(), self.origin)
        self.assertEqual(self.writes, [])

    def test_missing_or_wrong_csrf_is_rejected(self):
        for fields in ({"token": self.token}, {"csrf": "wrong", "token": self.token}):
            with self.assertRaisesRegex(SafeError, "token_import_form_rejected"):
                self.intake.accept(self.headers, urllib.parse.urlencode(fields).encode(), self.origin)
        self.assertEqual(self.writes, [])

    def test_duplicate_and_unexpected_fields_are_rejected(self):
        for suffix in (b"&token=another", b"&extra=value"):
            with self.assertRaisesRegex(SafeError, "token_import_form_rejected"):
                self.intake.accept(self.headers, self.body() + suffix, self.origin)
        self.assertEqual(self.writes, [])

    def test_header_injection_and_oversized_input_are_rejected(self):
        for value in ("short", "x" * 20 + "\r\nHeader: bad", "x" * 20001):
            with self.assertRaises(SafeError):
                self.intake.accept(self.headers, urllib.parse.urlencode({"csrf": self.intake.csrf, "token": value}).encode(), self.origin)
        self.assertEqual(self.writes, [])

    def test_keychain_failure_does_not_expose_exception_or_token(self):
        def failing(*args):
            raise RuntimeError(self.token)
        self.intake.writer = failing
        with self.assertRaises(SafeError) as raised:
            self.intake.accept(self.headers, self.body(), self.origin)
        self.assertEqual(str(raised.exception), "keychain_token_write_failed")
        self.assertFalse(self.intake.stored)

    def test_second_submission_cannot_overwrite_existing_import(self):
        self.intake.accept(self.headers, self.body(), self.origin)
        with self.assertRaisesRegex(SafeError, "token_import_already_completed"):
            self.intake.accept(self.headers, self.body(), self.origin)
        self.assertEqual(len(self.writes), 1)

    def test_platform_is_limited_to_meta_accounts(self):
        with self.assertRaisesRegex(SafeError, "token_import_platform_invalid"):
            TokenIntake("youtube", lambda *args: None)
