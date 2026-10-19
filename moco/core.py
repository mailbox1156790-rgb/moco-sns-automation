import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


class SafeError(Exception):
    """Only fixed, secret-free messages may be passed to this exception."""


def now():
    return dt.datetime.now(UTC).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()


def settings(root=ROOT):
    cfg = json.loads((root / "config/settings.json").read_text())
    local = root / "config/local.json"
    if local.exists():
        def merge(a, b):
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    merge(a[k], v)
                else:
                    a[k] = v
        merge(cfg, json.loads(local.read_text()))
    if cfg["mode"] not in {"draft_only", "threads_text"}:
        raise SafeError("unsupported_operation_mode")
    return cfg


def production_allowed(cfg, platform, video=False):
    policy = cfg.get("production", {})
    platforms = policy.get("platforms", ["threads", "instagram", "youtube"])
    if (not isinstance(platforms, list) or not platforms
            or any(p not in {"threads", "instagram", "youtube"} for p in platforms)):
        raise SafeError("production_settings_invalid")
    return platform in platforms and (not video or policy.get("video_enabled", True) is True)


class Store:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.var = self.root / "var"
        self.var.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.var.chmod(0o700)
        self.db = sqlite3.connect(str(self.var / "state.sqlite3"), timeout=10)
        (self.var / "state.sqlite3").chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS posts (
          id TEXT PRIMARY KEY, platform TEXT NOT NULL, fingerprint TEXT UNIQUE NOT NULL,
          content TEXT NOT NULL, revision TEXT NOT NULL, state TEXT NOT NULL,
          scheduled_at TEXT, approved_digest TEXT, attempts INTEGER NOT NULL DEFAULT 0,
          next_attempt TEXT, error_code TEXT, remote_id TEXT, remote_url TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
          n INTEGER PRIMARY KEY, post_id TEXT, event TEXT NOT NULL, at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS commands (
          issue_id INTEGER PRIMARY KEY, issue_number INTEGER NOT NULL, body_hash TEXT NOT NULL,
          status TEXT NOT NULL, result TEXT, comment_id INTEGER, created_at TEXT NOT NULL,
          command_id TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metrics (
          n INTEGER PRIMARY KEY, post_id TEXT NOT NULL, source TEXT NOT NULL,
          collected_at TEXT NOT NULL, payload TEXT NOT NULL
        );
        ''')
        if "command_id" not in [r[1] for r in self.db.execute("PRAGMA table_info(commands)")]:
            self.db.execute("ALTER TABLE commands ADD COLUMN command_id TEXT")
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS commands_command_id ON commands(command_id)")
        self.db.commit()

    def close(self):
        self.db.close()

    @contextlib.contextmanager
    def lock(self):
        with (self.var / "worker.lock").open("a") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SafeError("Another worker is active.") from None
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    @property
    def stopped(self):
        return (self.var / "STOP").exists()

    def stop(self):
        (self.var / "STOP").touch(mode=0o600)

    def resume(self):
        (self.var / "STOP").unlink(missing_ok=True)

    def event(self, post_id, event):
        self.db.execute("INSERT INTO events(post_id,event,at) VALUES(?,?,?)", (post_id, event, now()))

    def get(self, post_id):
        if not re.fullmatch(r"moco-[0-9a-f]{16}", post_id):
            raise SafeError("Invalid management ID.")
        row = self.db.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
        if not row:
            raise SafeError("Management ID not found.")
        return dict(row)

    def add(self, platform, content):
        if platform not in {"threads", "instagram", "youtube"}:
            raise SafeError("Unknown platform.")
        fp = digest({"platform": platform, "content": content})
        old = self.db.execute("SELECT id FROM posts WHERE fingerprint=?", (fp,)).fetchone()
        if old:
            return self.get(old["id"])
        post_id = "moco-" + uuid.uuid4().hex[:16]
        self.db.execute('''INSERT INTO posts
          (id,platform,fingerprint,content,revision,state,created_at,updated_at)
          VALUES(?,?,?,?,?,'awaiting_review',?,?)''',
          (post_id, platform, fp, canonical(content), fp, now(), now()))
        self.event(post_id, "draft_created")
        self.db.commit()
        return self.get(post_id)

    def asset_dir(self, post_id):
        self.get(post_id)
        p = self.var / "assets" / post_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def bundle_digest(self, post_id):
        row = self.get(post_id)
        p = self.asset_dir(post_id)
        files = {}
        names = ["draft.json", "post.txt"] if row["platform"] == "threads" else ["draft.json", "cover.png", "video.mp4"]
        for name in names:
            file = p / name
            if not file.is_file():
                raise SafeError("Render the draft before reviewing it.")
            files[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        try:
            if canonical(json.loads((p / "draft.json").read_text())) != row["content"]:
                raise SafeError("Rendered content is outdated. Render the current revision.")
            if row["platform"] == "threads" and (p / "post.txt").read_text() != json.loads(row["content"])["caption"]:
                raise SafeError("threads_text_artifact_does_not_match_draft")
        except (ValueError, OSError):
            raise SafeError("Rendered draft manifest is invalid.") from None
        return digest({"revision": row["revision"], "files": files})

    def revise(self, post_id, content):
        row = self.get(post_id)
        if row["state"] not in {"awaiting_review", "approved", "scheduled", "failed", "simulated"}:
            raise SafeError("published_or_inflight_record_is_immutable")
        validate_draft(content)
        fp = digest({"platform": row["platform"], "content": content})
        duplicate = self.db.execute("SELECT id FROM posts WHERE fingerprint=? AND id<>?", (fp, post_id)).fetchone()
        if duplicate:
            raise SafeError("Duplicate draft already exists.")
        self.db.execute("UPDATE posts SET content=?,revision=?,fingerprint=?,state='awaiting_review',approved_digest=NULL,scheduled_at=NULL,attempts=0,next_attempt=NULL,error_code=NULL,updated_at=? WHERE id=?", (canonical(content), fp, fp, now(), post_id))
        self.event(post_id, "draft_revised_approval_reset")
        self.db.commit()

    def approve(self, post_id, reviewed_digest):
        row = self.get(post_id)
        if row["state"] not in {"awaiting_review", "approved", "scheduled"}:
            raise SafeError("This state cannot be approved.")
        if self.bundle_digest(post_id) != reviewed_digest:
            raise SafeError("Review digest changed. Review the current files.")
        self.db.execute("UPDATE posts SET state='approved',approved_digest=?,scheduled_at=NULL,updated_at=? WHERE id=?", (reviewed_digest, now(), post_id))
        self.event(post_id, "local_owner_draft_approval")
        self.db.commit()

    def schedule(self, post_id, when):
        row = self.get(post_id)
        if row["state"] != "approved" or row["approved_digest"] != self.bundle_digest(post_id):
            raise SafeError("Current draft approval is required.")
        try:
            date = dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
            if date.tzinfo is None or date <= dt.datetime.now(UTC):
                raise ValueError()
        except ValueError:
            raise SafeError("Use a future ISO 8601 time with timezone, e.g. +09:00.") from None
        self.db.execute("UPDATE posts SET state='scheduled',scheduled_at=?,updated_at=? WHERE id=?", (date.astimezone(UTC).isoformat(), now(), post_id))
        self.event(post_id, "scheduled_simulation_only")
        self.db.commit()

    def summary(self):
        return [dict(r) for r in self.db.execute("SELECT id,platform,state,scheduled_at,attempts,error_code,remote_id,remote_url FROM posts ORDER BY created_at")]


def make_draft(topic):
    if not isinstance(topic, str) or not 1 <= len(topic.strip()) <= 100 or any(ord(c) < 32 for c in topic):
        raise SafeError("Topic must be 1–100 plain text characters.")
    topic = topic.strip()
    return {
        "topic": topic,
        "title": topic,
        "planning": {"goal": "役立つ手順を1つ持ち帰ってもらう", "status": "本人・事実確認待ち", "source_urls": [], "claims_verified": False},
        "script": [f"{topic}。まず、何を伝えたいかを一つに絞ってみよう。", "誰に届けたい？ 見た人にどうなってほしい？ 最初にメモしてみて。", "短く試して、反応を見てから見直そう。気づいたことを一つずつ残してね。"],
        "slides": [topic, "伝えたいことを\n一つに絞る", "誰に届けたい？\nどんな一歩にする？", "短く試す → 振り返る\n気づきをメモ"],
        "caption": f"{topic}\nまずは伝えたいことを一つに。小さく試して、気づきを残してみよう。\nあなたなら何から始める？",
        "disclosure": "ローカル検証用のテンプレート原稿。本人の経験や実績を表すものではありません。",
        "checks": {"owner_reviewed": False, "facts_checked": False, "rights_checked": False}
    }


def validate_draft(content):
    expected = set(make_draft("test"))
    if not isinstance(content, dict) or set(content) != expected:
        raise SafeError("invalid_draft_fields")
    for name, limit in [("topic", 100), ("title", 100), ("caption", 2200), ("disclosure", 1000)]:
        if not isinstance(content[name], str) or not 1 <= len(content[name]) <= limit:
            raise SafeError("invalid_draft_text_length")
    for key, limit in [("script", 1000), ("slides", 100)]:
        lines = content[key]
        if not isinstance(lines, list) or not 1 <= len(lines) <= 8 or any(not isinstance(x, str) or not 1 <= len(x) <= limit for x in lines):
            raise SafeError("invalid_draft_script_or_slides")
    if len(canonical(content)) > 20000:
        raise SafeError("draft_too_large")
