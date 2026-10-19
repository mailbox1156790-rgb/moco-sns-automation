import base64
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import uuid

from .core import ROOT, SafeError, UTC, canonical, now
from .net import HTTP, endpoint

REPOSITORY = "mailbox1156790-rgb/moco-sns-automation"


class GitHub:
    def __init__(self, cfg, root=ROOT, http=None):
        if cfg["repository"] != REPOSITORY:
            raise SafeError("GitHub repository is pinned in this release.")
        self.cfg = cfg
        self.http = http or HTTP()
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        try:
            r = subprocess.run(["git", "credential", "fill"], cwd=str(root),
                 input=f"protocol=https\nhost=github.com\npath={REPOSITORY}.git\n\n", text=True,
                 capture_output=True, timeout=30, env=env, check=True)
            fields = dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)
            self._token = fields["password"]
        except (OSError, subprocess.SubprocessError, KeyError):
            try:
                r = subprocess.run(["/usr/local/bin/gh", "auth", "token", "--hostname", "github.com"],
                    capture_output=True, text=True, timeout=30, check=True)
                self._token = r.stdout.strip()
                if not self._token:
                    raise ValueError()
            except (OSError, subprocess.SubprocessError, ValueError):
                raise SafeError("github_authentication_unavailable") from None

    def call(self, method, path, body=None):
        if not path.startswith(("/repos/" + REPOSITORY + "/", "/repos/" + REPOSITORY + "?")) and path not in {"/user", "/repos/" + REPOSITORY}:
            raise SafeError("github_path_blocked")
        return self.http.json(method, "https://api.github.com" + path, self._token, body,
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"})

    def identity(self):
        user = self.call("GET", "/user")
        repo = self.call("GET", "/repos/" + REPOSITORY)
        return {"login": user["login"], "id": user["id"], "repository": repo["full_name"],
                "private": repo["private"], "push": bool(repo.get("permissions", {}).get("push")),
                "issues_enabled": repo.get("has_issues", False)}

    def issues(self):
        # Drain in created order; repeated polls use the durable issue-id ledger.
        result = []
        for page in range(1, 11):
            path = f"/repos/{REPOSITORY}/issues?state=open&labels={self.cfg['command_label'].replace(':', '%3A')}&per_page=100&page={page}&sort=created&direction=asc"
            batch = self.call("GET", path)
            result.extend(x for x in batch if "pull_request" not in x)
            if len(batch) < 100:
                break
        return result

    def comments(self, number):
        result = []
        for page in range(1, 101):
            batch = self.call("GET", f"/repos/{REPOSITORY}/issues/{int(number)}/comments?per_page=100&page={page}")
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise SafeError("github_comment_limit_reached")

    def report(self, number, issue_id, result):
        marker = f"<!-- moco-command:{int(issue_id)} -->"
        for comment in self.comments(number):
            if marker in (comment.get("body") or "") and comment["user"]["id"] in self.cfg["trusted_actor_ids"]:
                return comment["id"]
        body = marker + "\nMac実行結果（公開投稿なし）\n```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```"
        return self.call("POST", f"/repos/{REPOSITORY}/issues/{int(number)}/comments", {"body": body})["id"]

    def verify_editor(self, issue):
        # REST's issue author alone does not identify a collaborator who edited the body.
        query = '''query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){issue(number:$number){body lastEditedAt author{... on User{databaseId}} editor{... on User{databaseId}}}}}'''
        response = self.http.json("POST", "https://api.github.com/graphql", self._token, {
            "query": query, "variables": {"owner": REPOSITORY.split('/')[0], "name": REPOSITORY.split('/')[1], "number": issue["number"]}})
        try:
            data = response["data"]["repository"]["issue"]
            if data["body"] != (issue.get("body") or "") or data["author"]["databaseId"] not in self.cfg["trusted_actor_ids"]:
                raise SafeError("command_changed_or_untrusted")
            if data["lastEditedAt"] and (data.get("editor") or {}).get("databaseId") not in self.cfg["trusted_actor_ids"]:
                raise SafeError("command_untrusted_editor")
        except (KeyError, TypeError):
            raise SafeError("command_editor_could_not_be_verified") from None


def parse_command(issue, cfg):
    if issue.get("pull_request") or issue.get("state") != "open":
        raise SafeError("command_not_open_issue")
    if issue.get("user", {}).get("id") not in cfg["trusted_actor_ids"]:
        raise SafeError("command_untrusted_author")
    if cfg["command_label"] not in [x.get("name") for x in issue.get("labels", [])]:
        raise SafeError("command_label_missing")
    try:
        updated = dt.datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))
        if updated.tzinfo is None or not dt.datetime.now(UTC) - dt.timedelta(days=cfg["max_command_age_days"]) <= updated <= dt.datetime.now(UTC) + dt.timedelta(minutes=5):
            raise ValueError()
    except (KeyError, ValueError):
        raise SafeError("command_stale_or_invalid_time") from None
    body = issue.get("body") or ""
    if len(body) > 4096:
        raise SafeError("command_body_too_large")
    body = body.strip()
    if body.startswith("```json\n") and body.endswith("\n```"):
        body = body[8:-4]
    try:
        command = json.loads(body)
        if not isinstance(command, dict) or command.get("version") != 1:
            raise ValueError()
        command_id = str(uuid.UUID(command["command_id"]))
        if command_id != command["command_id"]:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise SafeError("command_invalid_json_or_version") from None
    action = command.get("action")
    keys = {"version", "command_id", "action"}
    if action == "draft":
        keys |= {"topic", "platform"}
        if command.get("platform") not in {"youtube", "instagram", "threads"}:
            raise SafeError("command_invalid_platform")
        topic = command.get("topic")
        if not isinstance(topic, str) or not 1 <= len(topic.strip()) <= 100 or any(ord(x) < 32 for x in topic):
            raise SafeError("command_invalid_topic")
    elif action == "render":
        keys.add("id")
        if not re.fullmatch(r"moco-[0-9a-f]{16}", str(command.get("id", ""))):
            raise SafeError("command_invalid_post_id")
    elif action not in {"status", "analyze", "stop"}:
        raise SafeError("command_action_not_allowed")
    if set(command) != keys:
        raise SafeError("command_unknown_or_missing_fields")
    return command


def poll(store, cfg, execute, client=None):
    github_cfg = cfg["github"]
    if not github_cfg["trusted_actor_ids"]:
        raise SafeError("github_trusted_actor_not_configured")
    client = client or GitHub(github_cfg, store.root)
    # The ledger stores no raw issue text, credentials, command arguments or exception details.
    for issue in client.issues():
        if store.db.execute("SELECT 1 FROM commands WHERE issue_id=?", (issue["id"],)).fetchone():
            continue
        try:
            command = parse_command(issue, github_cfg)
            client.verify_editor(issue)
        except SafeError:
            continue
        if store.db.execute("SELECT 1 FROM commands WHERE command_id=?", (command["command_id"],)).fetchone():
            continue
        if store.stopped and command["action"] not in {"stop", "status", "analyze"}:
            continue
        # Reserve once before side effects. A crash requires local reconciliation, never replay.
        store.db.execute("INSERT INTO commands VALUES(?,?,?,'running',NULL,NULL,?,?)", (issue["id"], issue["number"], hashlib.sha256(issue["body"].encode()).hexdigest(), now(), command["command_id"]))
        store.db.commit()
        try:
            result = execute(command)
        except SafeError as e:
            result = {"status": "failed", "error_code": str(e), "public": False}
        except Exception:
            result = {"status": "failed", "error_code": "unexpected_local_error", "public": False}
        store.db.execute("UPDATE commands SET status='executed',result=? WHERE issue_id=?", (canonical(result), issue["id"]))
        store.db.commit()
    for row in store.db.execute("SELECT * FROM commands WHERE status='executed' AND comment_id IS NULL").fetchall():
        comment_id = client.report(row["issue_number"], row["issue_id"], json.loads(row["result"]))
        store.db.execute("UPDATE commands SET status='reported',comment_id=? WHERE issue_id=?", (comment_id, row["issue_id"]))
        store.db.commit()
    return {"status": "ok", "commands_total": store.db.execute("SELECT count(*) FROM commands").fetchone()[0], "public": False}
