import base64
import hashlib
import http.server
import json
from pathlib import Path
import secrets
import time
import urllib.parse
import webbrowser

from .accounts import Secrets
from .core import ROOT, SafeError
from .net import HTTP

AUTH_WAIT_SECONDS = 60 * 60


def youtube_authorize(client_file, root=ROOT):
    """Local browser consent with PKCE/state; no HTTP access logs or auth URLs printed."""
    try:
        client = json.loads(Path(client_file).read_text())["installed"]
        client_id, client_secret = client["client_id"], client["client_secret"]
    except (OSError, ValueError, KeyError):
        raise SafeError("desktop_oauth_client_file_invalid") from None
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            params = urllib.parse.parse_qs(url.query)
            if url.path != "/callback" or params.get("state") != [state]:
                self.send_response(400)
                self.end_headers()
                return
            if "code" in params:
                result["code"] = params["code"][0]
            else:
                result["denied"] = True
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write("認証結果をMacで処理しています。このタブを閉じてください。".encode())

    with http.server.HTTPServer(("127.0.0.1", 0), Handler) as server:
        server.timeout = 1
        redirect = f"http://127.0.0.1:{server.server_port}/callback"
        # Phase 1 requests read-only access. Upload access must be reviewed in phase 2.
        scopes = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
            "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": " ".join(scopes),
            "access_type": "offline", "prompt": "consent", "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
        if not webbrowser.open(url):
            raise SafeError("could_not_open_authorization_browser")
        # Account selection and owner consent can span several chat turns.
        # Keep the loopback receiver alive while the owner completes those steps.
        deadline = time.monotonic() + AUTH_WAIT_SECONDS
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if result.get("denied"):
        raise SafeError("oauth_authorization_denied")
    if "code" not in result:
        raise SafeError("oauth_authorization_timed_out")
    response = HTTP().json("POST", "https://oauth2.googleapis.com/token", body={
        "client_id": client_id, "client_secret": client_secret, "code": result["code"],
        "code_verifier": verifier, "redirect_uri": redirect, "grant_type": "authorization_code"}, form=True)
    if not response.get("refresh_token"):
        raise SafeError("oauth_refresh_token_missing")
    Secrets(root).set("youtube", json.dumps({"client_id": client_id, "client_secret": client_secret,
                         "refresh_token": response["refresh_token"], "scope": response.get("scope")}))
    return {"status": "stored_in_macos_keychain", "access": "read_only"}
