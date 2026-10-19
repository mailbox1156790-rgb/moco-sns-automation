"""Owner-approved, text-only Threads delivery. No uncertain POST is replayed."""
import datetime as dt
import hashlib
import json
import re
import sqlite3
from urllib.parse import urlsplit

from .accounts import AccountAPI, Secrets
from .core import SafeError, UTC, now, production_allowed


class ThreadsWriteAPI(AccountAPI):
    def __init__(self, cfg):
        class PublishCredential:
            def get(self, platform):
                return Secrets().get("threads_publish")
        super().__init__("threads", cfg, secrets=PublishCredential())

    def create(self, text):
        return self.http.json("POST", self.base + "/me/threads", self.token,
            {"media_type": "TEXT", "text": text, "auto_publish_text": "false"}, form=True)

    def publish(self, container_id):
        return self.http.json("POST", self.base + "/me/threads_publish", self.token,
            {"creation_id": container_id}, form=True)


def table(store):
    store.db.execute('''CREATE TABLE IF NOT EXISTS threads_deliveries (
        post_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, text_hash TEXT NOT NULL,
        review_digest TEXT NOT NULL, not_before TEXT NOT NULL, state TEXT NOT NULL,
        container_id TEXT, remote_id TEXT, error_code TEXT, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, UNIQUE(account_id,text_hash))''')
    store.db.commit()


def text_and_target(store, cfg, post_id):
    row = store.get(post_id)
    account = cfg["accounts"]["threads"]
    if row["platform"] != "threads" or not production_allowed(cfg, "threads"):
        raise SafeError("threads_text_only_required")
    if not account.get("owner_confirmed") or not re.fullmatch(r"[0-9]+", str(account.get("account_id", ""))):
        raise SafeError("owner_confirmed_pinned_account_required")
    text = json.loads(row["content"]).get("caption")
    if (not isinstance(text, str) or not 1 <= len(text) <= 500 or not text.strip()
            or any(ord(c) < 32 and c != "\n" for c in text)):
        raise SafeError("threads_plain_text_must_be_1_to_500_characters")
    return row, text, str(account["account_id"])


def approve_threads(store, cfg, post_id, review_digest, when):
    """Caller must hold the lock and have obtained the owner's content/time approval."""
    if store.stopped:
        raise SafeError("local_stop_is_active")
    row, text, target = text_and_target(store, cfg, post_id)
    if store.bundle_digest(post_id) != review_digest:
        raise SafeError("threads_review_digest_changed")
    try:
        when_dt = dt.datetime.now(UTC) if when == "now" else dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
        if when_dt.tzinfo is None or (when != "now" and when_dt <= dt.datetime.now(UTC)):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise SafeError("threads_time_must_be_now_or_future_with_timezone") from None
    table(store)
    old = store.db.execute("SELECT * FROM threads_deliveries WHERE post_id=?", (post_id,)).fetchone()
    if old and old["state"] != "approved":
        raise SafeError("threads_delivery_already_started")
    if row["state"] not in {"awaiting_review", "approved", "scheduled"}:
        raise SafeError("threads_draft_not_approvable")
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    try:
        store.db.execute('''INSERT INTO threads_deliveries
            (post_id,account_id,text_hash,review_digest,not_before,state,created_at,updated_at)
            VALUES(?,?,?,?,?,'approved',?,?) ON CONFLICT(post_id) DO UPDATE SET
            account_id=excluded.account_id,text_hash=excluded.text_hash,
            review_digest=excluded.review_digest,not_before=excluded.not_before,updated_at=excluded.updated_at''',
            (post_id, target, text_hash, review_digest, when_dt.astimezone(UTC).isoformat(), now(), now()))
    except sqlite3.IntegrityError:
        store.db.rollback()
        raise SafeError("threads_duplicate_text_delivery_blocked") from None
    store.db.execute("UPDATE posts SET state=?,approved_digest=?,scheduled_at=?,updated_at=? WHERE id=?",
        ("approved" if when == "now" else "scheduled", review_digest,
         None if when == "now" else when_dt.astimezone(UTC).isoformat(), now(), post_id))
    store.event(post_id, "owner_approved_threads_text_destination_and_time")
    store.db.commit()
    return {"id": post_id, "account_id": target, "not_before": when_dt.isoformat(),
            "state": "approved" if when == "now" else "scheduled", "public": False}


def result(store, post_id):
    row = store.get(post_id)
    return {"id": post_id, "state": row["state"], "remote_id": row["remote_id"],
            "remote_url": row["remote_url"], "error_code": row["error_code"],
            "public": row["state"] == "published"}


def mark(store, post_id, state, error=None, **fields):
    # Only fixed internal field names and error codes enter the journal.
    if set(fields) - {"container_id", "remote_id"}:
        raise SafeError("threads_journal_field_invalid")
    assignments = "".join("," + key + "=?" for key in fields)
    store.db.execute("UPDATE threads_deliveries SET state=?,error_code=?,updated_at=?" + assignments + " WHERE post_id=?",
                     (state, error, now(), *fields.values(), post_id))
    store.db.execute("UPDATE posts SET state=?,error_code=?,updated_at=? WHERE id=?", (state, error, now(), post_id))
    store.db.commit()


def numeric_id(response):
    value = str(response.get("id", "")) if isinstance(response, dict) else ""
    if not re.fullmatch(r"[0-9]{1,100}", value):
        raise SafeError("threads_response_id_missing")
    return value


def publish_threads(store, cfg, post_id, client=None):
    """Caller holds lock. A pre-existing owner approval is mandatory, including on restart."""
    job = cfg.get("publishing", {}).get("threads", {})
    if (cfg.get("mode") != "threads_text" or job.get("enabled") is not True
            or job.get("permission_owner_approved") is not True):
        raise SafeError("threads_publication_not_enabled_by_owner")
    if store.stopped:
        raise SafeError("local_stop_is_active")
    table(store)
    row, text, target = text_and_target(store, cfg, post_id)
    delivery = store.db.execute("SELECT * FROM threads_deliveries WHERE post_id=?", (post_id,)).fetchone()
    if not delivery:
        raise SafeError("threads_destination_content_and_time_approval_required")
    if row["state"] == "published":
        return result(store, post_id)
    if (delivery["account_id"] != target or delivery["review_digest"] != row["approved_digest"]
            or delivery["review_digest"] != store.bundle_digest(post_id)
            or delivery["text_hash"] != hashlib.sha256(text.encode()).hexdigest()):
        raise SafeError("threads_approval_binding_changed")
    if dt.datetime.now(UTC) < dt.datetime.fromisoformat(delivery["not_before"]):
        return {"id": post_id, "state": "waiting_for_approved_time", "public": False}
    if delivery["state"] in {"creating", "publishing", "reconciliation_required"}:
        mark(store, post_id, "reconciliation_required", "threads_uncertain_post_not_replayed")
        return result(store, post_id)
    client = client or ThreadsWriteAPI(cfg)

    def recheck():
        if store.stopped:
            raise SafeError("local_stop_is_active")
        if store.bundle_digest(post_id) != delivery["review_digest"]:
            raise SafeError("threads_review_digest_changed")
        identity = client.identity()
        if str(identity["account_id"]) != target:
            raise SafeError("authenticated_account_id_mismatch")
        profile = urlsplit(cfg["accounts"]["threads"].get("profile_url", ""))
        if (profile.scheme != "https" or profile.hostname not in {"www.threads.com", "threads.com", "www.threads.net", "threads.net"}
                or profile.path.rstrip("/") != "/@" + identity["username"]):
            raise SafeError("threads_profile_does_not_match_authenticated_identity")
        return identity

    identity = recheck()
    container = delivery["container_id"]
    remote = delivery["remote_id"]
    if delivery["state"] == "approved":
        mark(store, post_id, "creating")  # Durable before every non-idempotent request.
        if store.stopped:
            mark(store, post_id, "approved")
            raise SafeError("local_stop_is_active")
        try:
            container = numeric_id(client.create(text))
        except Exception:
            mark(store, post_id, "reconciliation_required", "threads_create_outcome_unverified")
            return result(store, post_id)
        mark(store, post_id, "container_ready", container_id=container)
    if not remote:
        status = client.get("/" + container, {"fields": "status"}).get("status")
        if status == "IN_PROGRESS":
            return {"id": post_id, "state": "waiting_for_container", "public": False}
        if status != "FINISHED":
            mark(store, post_id, "reconciliation_required", "threads_container_not_publishable")
            return result(store, post_id)
        identity = recheck()
        mark(store, post_id, "publishing")
        if store.stopped:
            mark(store, post_id, "container_ready")
            raise SafeError("local_stop_is_active")
        try:
            remote = numeric_id(client.publish(container))
        except Exception:
            mark(store, post_id, "reconciliation_required", "threads_publish_outcome_unverified")
            return result(store, post_id)
        mark(store, post_id, "verification_required", remote_id=remote)
        store.db.execute("UPDATE posts SET remote_id=? WHERE id=?", (remote, post_id))
        store.db.commit()
    try:
        post = client.get("/" + remote, {"fields": "id,username,text,permalink,media_type"})
        link = urlsplit(post.get("permalink", ""))
        if (numeric_id(post) != remote or post.get("username") != identity["username"]
                or post.get("text") != text or post.get("media_type") != "TEXT_POST"
                or link.scheme != "https" or link.hostname not in {"www.threads.com", "threads.com", "www.threads.net", "threads.net"}
                or link.username or link.password or link.port not in {None, 443}
                or not link.path.startswith("/@" + identity["username"] + "/post/")):
            raise SafeError("threads_public_post_does_not_match_approval")
        # Check numeric ownership via the same authenticated user's post list.
        listing = client.get("/" + target + "/threads", {"fields": "id,permalink", "limit": 100})
        if not any(str(x.get("id")) == remote and x.get("permalink") == post["permalink"] for x in listing.get("data", [])):
            raise SafeError("threads_post_ownership_not_verified")
    except Exception:
        mark(store, post_id, "verification_required", "threads_public_result_verification_pending")
        return result(store, post_id)
    store.db.execute("UPDATE posts SET state='published',remote_id=?,remote_url=?,error_code=NULL,updated_at=? WHERE id=?", (remote, post["permalink"], now(), post_id))
    store.db.execute("UPDATE threads_deliveries SET state='published',error_code=NULL,updated_at=? WHERE post_id=?", (now(), post_id))
    store.event(post_id, "threads_public_id_url_text_and_owner_verified")
    store.db.commit()
    return result(store, post_id)
