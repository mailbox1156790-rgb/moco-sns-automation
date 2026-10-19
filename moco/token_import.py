# -*- coding: utf-8 -*-
"""Short-lived loopback form -> Keychain. No tokens in URLs, files or logs."""
import html
import http.server
import json
import re
import secrets
import time
import urllib.parse

from .accounts import Secrets
from .core import SafeError

MAX_BODY = 20000
WAIT_SECONDS = 3600
CSP = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
REFERRER_POLICY = "same-origin"


class TokenIntake:
    def __init__(self, platform, writer):
        if platform not in {"instagram", "threads", "threads_publish"}:
            raise SafeError("token_import_platform_invalid")
        self.platform, self.writer = platform, writer
        self.csrf = secrets.token_urlsafe(32)
        self.stored = False

    def accept(self, headers, raw, origin):
        if self.stored:
            raise SafeError("token_import_already_completed")
        if (headers.get("Origin") != origin or headers.get("Host") != origin.split("//", 1)[1]
                or headers.get("Content-Type", "").split(";", 1)[0] != "application/x-www-form-urlencoded"
                or len(raw) > MAX_BODY):
            raise SafeError("token_import_request_rejected")
        try:
            fields = urllib.parse.parse_qs(raw.decode("ascii"), keep_blank_values=True,
                strict_parsing=True, max_num_fields=3)
            if set(fields) != {"csrf", "token"} or any(len(v) != 1 for v in fields.values()):
                raise ValueError()
            if not secrets.compare_digest(fields["csrf"][0], self.csrf):
                raise ValueError()
            value = fields["token"][0]
            if not re.fullmatch(r"[A-Za-z0-9._~+/=-]{20,16384}", value):
                raise ValueError()
        except (ValueError, UnicodeError, TypeError):
            raise SafeError("token_import_form_rejected") from None
        try:
            self.writer(self.platform, value)
        except Exception:
            raise SafeError("keychain_token_write_failed") from None
        self.stored = True
        return {"status": "stored_in_macos_keychain", "platform": self.platform,
            "replaced_existing": False, "api_identity_verified": False, "public": False}

    def page(self):
        label = "Threads投稿用トークン" if self.platform == "threads_publish" else "読み取りトークン"
        return '''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>もこ SNS 認証をMacへ保存</title>
<style>body{font:18px system-ui;max-width:620px;margin:70px auto;padding:24px;color:#182239}
input{box-sizing:border-box;width:100%;padding:14px;font-size:18px}button{padding:14px;margin-top:20px;font-size:18px}
p{line-height:1.7}</style>
<h1>もこ専用の認証をMacへ保存</h1><p>対象：''' + html.escape(self.platform) + '''</p>
<p>Metaの公式画面で生成した、もこ専用アプリの''' + label + '''を貼り付けます。
保存先はこのMacのKeychainです。既存の認証情報は上書きしません。</p>
<form method="post" action="/import" autocomplete="off">
<input type="hidden" name="csrf" value="''' + html.escape(self.csrf, quote=True) + '''">
<label for="token">''' + label + '''（非表示）</label>
<input id="token" type="password" name="token" autocomplete="off" spellcheck="false" required minlength="20" maxlength="16384">
<button type="submit">このMacのKeychainへ保存</button></form>
<p>トークンをチャットやGitHubへ貼らないでください。保存後に接続先アカウントをAPIで確認します。</p></html>'''


def receive_token(platform, writer=None):
    intake = TokenIntake(platform, writer or Secrets().add)
    result = None

    class Handler(http.server.BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass

        def send_page(self, status, body):
            encoded = body.encode("utf-8")
            self.send_response(status)
            for key, value in {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store",
                    # no-referrer makes Chromium send Origin: null on form POST.
                    # Preserve the same-origin Origin check; disclose no referrer
                    # to other origins and never include a secret in this URL.
                    "Referrer-Policy": REFERRER_POLICY, "Content-Security-Policy": CSP,
                    "X-Content-Type-Options": "nosniff", "Content-Length": str(len(encoded))}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path != "/" or self.headers.get("Host") != origin.split("//", 1)[1]:
                self.send_page(404, "Page unavailable")
                return
            self.send_page(200, intake.page())

        def do_POST(self):
            nonlocal result
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if self.path != "/import" or not 0 < size <= MAX_BODY:
                    raise SafeError("token_import_request_rejected")
                result = intake.accept(self.headers, self.rfile.read(size), origin)
            except Exception:
                self.send_page(400, '<meta charset="utf-8">保存できませんでした。既存の認証情報と入力内容をMacで確認してください。')
                return
            self.send_page(200, '<meta charset="utf-8"><h1>MacのKeychainへ保存しました</h1><p>接続先アカウントのAPI照合はこれから行います。トークンの表示や共有は不要です。</p>')

    class Server(http.server.HTTPServer):
        def handle_error(self, request, address):
            # No request contents, traceback or exception values in terminal logs.
            pass

    with Server(("127.0.0.1", 0), Handler) as server:
        origin = "http://127.0.0.1:" + str(server.server_port)
        server.timeout = 0.5
        print(json.dumps({"status": "ready", "origin": origin, "platform": platform}), flush=True)
        deadline = time.monotonic() + WAIT_SECONDS
        while not intake.stored and time.monotonic() < deadline:
            server.handle_request()
    if not result:
        raise SafeError("token_import_timed_out")
    return result
