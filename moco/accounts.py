import datetime as dt
import json
import re

from .core import ROOT, SafeError, now
from .media import native_call
from .net import HTTP, endpoint


class Secrets:
    def __init__(self, root=ROOT):
        self.root = root

    def get(self, platform):
        try:
            return native_call("secret-get", {"account": platform}, self.root).decode()
        except SafeError:
            raise SafeError("keychain_credential_unavailable") from None

    def set(self, platform, value):
        native_call("secret-set", {"account": platform, "value": value}, self.root)


class AccountAPI:
    """Read-only official API adapters. Publishing is intentionally absent in phase 1."""
    def __init__(self, platform, cfg, secrets=None, http=None):
        self.platform, self.cfg = platform, cfg
        self.account = cfg["accounts"][platform]
        self.http, self.secrets = http or HTTP(), secrets or Secrets()
        stored = self.secrets.get(platform)
        if platform == "youtube":
            try:
                auth = json.loads(stored)
                self.token = self.http.json("POST", "https://oauth2.googleapis.com/token", body={
                    "grant_type": "refresh_token", "client_id": auth["client_id"],
                    "client_secret": auth["client_secret"], "refresh_token": auth["refresh_token"]}, form=True)["access_token"]
            except (ValueError, KeyError):
                raise SafeError("youtube_oauth_record_invalid") from None
            self.base = "https://www.googleapis.com/youtube/v3"
        else:
            self.token = stored
            version = self.account.get("api_version")
            if platform == "instagram":
                if not version or not re.fullmatch(r"v[0-9]+\.0", version):
                    raise SafeError("instagram_api_version_must_be_verified_and_configured")
                self.base = "https://graph.instagram.com/" + version
            else:
                self.base = "https://graph.threads.net/v1.0"

    def get(self, path, params):
        return self.http.json("GET", endpoint(self.base, path, params), self.token)

    def identity(self):
        if self.platform == "youtube":
            mine = self.get("/channels", {"part": "id,snippet", "mine": "true"}).get("items", [])
            target = self.get("/channels", {"part": "id,snippet", "forHandle": self.account["handle"]}).get("items", [])
            if len(target) != 1 or not any(x["id"] == target[0]["id"] for x in mine):
                raise SafeError("youtube_authenticated_channel_does_not_match_target")
            result = {"platform": self.platform, "account_id": target[0]["id"], "handle": self.account["handle"]}
        else:
            r = self.get("/me", {"fields": "user_id,username" if self.platform == "instagram" else "id,username"})
            result = {"platform": self.platform, "account_id": r["user_id" if self.platform == "instagram" else "id"], "username": r["username"]}
        expected = self.account.get("account_id")
        if expected and str(expected) != str(result["account_id"]):
            raise SafeError("authenticated_account_id_mismatch")
        result["checked_at"] = now()
        return result

    def measured_metrics(self, remote_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", remote_id):
            raise SafeError("invalid_remote_id")
        identity = self.identity()
        if not self.account.get("owner_confirmed") or str(self.account.get("account_id")) != str(identity["account_id"]):
            raise SafeError("owner_confirmed_pinned_account_required")
        if self.platform == "youtube":
            rows = self.get("/videos", {"part": "id,snippet,statistics,status", "id": remote_id}).get("items", [])
            if len(rows) != 1 or rows[0]["snippet"]["channelId"] != identity["account_id"]:
                raise SafeError("remote_video_ownership_not_verified")
            values = rows[0].get("statistics", {})
            result = {"views": number(values.get("viewCount")), "likes": number(values.get("likeCount")),
                      "comments": number(values.get("commentCount")), "reach": None, "watch_time_minutes": None}
            url = "https://www.youtube.com/shorts/" + remote_id
            source = "youtube_data_api.videos.list"
        else:
            # Media ownership must be demonstrated in the authenticated user's paginated media list.
            path = "/" + identity["account_id"] + ("/threads" if self.platform == "threads" else "/media")
            after, found = None, None
            for _ in range(100):
                params = {"fields": "id,permalink", "limit": 100}
                if after:
                    params["after"] = after
                listing = self.get(path, params)
                found = next((x for x in listing.get("data", []) if str(x["id"]) == remote_id), None)
                if found:
                    break
                after = listing.get("paging", {}).get("cursors", {}).get("after") if listing.get("paging", {}).get("next") else None
                if not after:
                    break
            if not found:
                raise SafeError("remote_media_ownership_not_verified")
            requested = ["views", "likes", "replies", "reposts", "quotes", "shares"] if self.platform == "threads" else ["views", "reach", "likes", "comments", "saved", "shares"]
            result = {key: None for key in requested}
            for key in requested:
                try:
                    response = self.get("/" + remote_id + "/insights", {"metric": key})
                    metric = next((x for x in response.get("data", []) if x.get("name") == key), {})
                    values = metric.get("values", [])
                    value = values[-1].get("value") if values else metric.get("total_value", {}).get("value")
                    result[key] = number(value)
                except SafeError as e:
                    if str(e) not in {"http_status_400"}:
                        raise
                    # Unsupported metrics stay null. Authentication/rate-limit failures propagate.
            url = found.get("permalink")
            source = self.platform + "_api.insights"
        return {"platform": self.platform, "account_id": identity["account_id"], "remote_id": remote_id,
                "remote_url": url, "collected_at": now(), "source": source, "metrics": result,
                "missing_metrics": [k for k, v in result.items() if v is None]}


def number(value):
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
        return n if n >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None
