import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from .core import SafeError

ALLOWED_HOSTS = {"api.github.com", "www.googleapis.com", "youtubeanalytics.googleapis.com", "oauth2.googleapis.com", "graph.instagram.com", "graph.threads.net"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward Authorization to redirects, even on the same host.
        raise SafeError("http_redirect_blocked")


class HTTP:
    def __init__(self):
        self.context = ssl.create_default_context()
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.context), NoRedirect())

    def json(self, method, url, token=None, body=None, headers=None, form=False):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in {None, 443}:
            raise SafeError("http_destination_blocked")
        if any(k.lower() in {"access_token", "key", "client_secret", "refresh_token"} for k, v in urllib.parse.parse_qsl(parsed.query)):
            raise SafeError("secret_in_url_blocked")
        request_headers = {"User-Agent": "moco-sns-automation/0.1", "Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        if token:
            request_headers["Authorization"] = "Bearer " + token
        data = None
        if body is not None:
            data = (urllib.parse.urlencode(body) if form else json.dumps(body)).encode()
            request_headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        # Only idempotent GETs are retried automatically. No implicit POST replay.
        for attempt in range(3 if method == "GET" else 1):
            try:
                req = urllib.request.Request(url, data=data, method=method, headers=request_headers)
                with self.opener.open(req, timeout=30) as response:
                    payload = response.read(4 * 1024 * 1024 + 1)
                    if len(payload) > 4 * 1024 * 1024:
                        raise SafeError("http_response_too_large")
                    return json.loads(payload)
            except urllib.error.HTTPError as e:
                if method == "GET" and (e.code == 429 or 500 <= e.code < 600) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise SafeError("http_status_" + str(e.code)) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if method == "GET" and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise SafeError("http_network_or_tls_error") from None
            except (ValueError, UnicodeError):
                raise SafeError("http_invalid_json") from None


def endpoint(base, path, params=None):
    return base + path + ("?" + urllib.parse.urlencode(params) if params else "")
