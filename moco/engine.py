import datetime as dt
import json

from .core import SafeError, UTC, atomic_json, canonical, make_draft, now
from .media import render
from .collection import refresh_metrics
from .reporting import report_metrics_checkpoint


def analysis(store):
    latest = store.db.execute('''SELECT * FROM metrics WHERE n IN
        (SELECT max(n) FROM metrics GROUP BY post_id) ORDER BY n''').fetchall()
    measured = [json.loads(r["payload"]) for r in latest]
    report = {
        "generated_at": now(), "measured_samples": len(measured), "observations": measured,
        "missing": "未取得はnull。未取得の指標を0と解釈しない。媒体をまたいだ再生数比較は行わない。",
        "recommendations": ["本人確認後に同じ媒体・同じ公開後経過時間で実測を集め、冒頭の問いかけを一要素ずつ比較する。"] if measured else ["実績データ未取得。API認証と投稿IDの照合後に収集を始める。現時点では成果の良否を判定しない。"],
        "limitations": ["年齢・性別・維持率・収益・視聴時間は現在未取得。", "この版ではData API/Meta Insightsの取得値を保存。YouTube Analyticsの詳細レポート取込は次段階。", "観測値から因果関係を断定しない。"]
    }
    atomic_json(store.var / "reports/analysis.json", report)
    return {"measured_samples": len(measured), "report": "var/reports/analysis.json", "public": False}


def execute(store, cfg, command):
    action = command["action"]
    if store.stopped and action not in {"stop", "status", "analyze"}:
        raise SafeError("Stopped. Resume locally first.")
    if action == "draft":
        row = store.add(command["platform"], make_draft(command["topic"]))
        return {"id": row["id"], "state": row["state"], "platform": row["platform"], "public": False}
    if action == "render":
        return render_with_retry(store, cfg, command["id"])
    if action == "status":
        return {"mode": cfg["mode"], "stopped": store.stopped, "posts": store.summary(), "public": False}
    if action == "analyze":
        return analysis(store)
    if action == "stop":
        store.stop()
        return {"stopped": True, "public": False}
    raise SafeError("command_action_not_allowed")


def tick(store, cfg, github=False, client=None):
    from .github import poll
    with store.lock():
        if github:
            remote = poll(store, cfg, lambda c: execute(store, cfg, c), client)
        else:
            remote = None
        collection = refresh_metrics(store, cfg)
        if collection.get("updated_posts", 0):
            analysis(store)
        metrics_report = report_metrics_checkpoint(store, cfg) if github else None
        if not store.stopped:
            due = store.db.execute("SELECT * FROM posts WHERE state='scheduled' AND scheduled_at<=?", (now(),)).fetchall()
            for row in due:
                post_id = row["id"]
                # Full bytes, not just filenames, are bound to the local approval.
                try:
                    current_digest = store.bundle_digest(post_id)
                except SafeError:
                    current_digest = None
                if not current_digest or row["approved_digest"] != current_digest:
                    store.db.execute("UPDATE posts SET state='awaiting_review',approved_digest=NULL,scheduled_at=NULL,updated_at=? WHERE id=?", (now(), post_id))
                    store.event(post_id, "approval_invalidated")
                else:
                    # Never fabricate a remote ID or mark a local simulation as published.
                    store.db.execute("UPDATE posts SET state='simulated',updated_at=? WHERE id=?", (now(), post_id))
                    store.event(post_id, "scheduled_dry_run_completed_no_network_publish")
            retries = store.db.execute("SELECT * FROM posts WHERE state='failed' AND next_attempt<=? AND attempts<?", (now(), cfg["retry"]["max_attempts"])).fetchall()
            for row in retries:
                if store.stopped:
                    break
                render_with_retry(store, cfg, row["id"])
            store.db.commit()
        result = {"checked_at": now(), "mode": cfg["mode"], "stopped": store.stopped, "posts": store.summary(), "github": remote, "collection": collection, "github_metrics_report": metrics_report, "public": False}
        atomic_json(store.var / "reports/status.json", result)
        return result


def render_with_retry(store, cfg, post_id):
    try:
        return render(store, post_id, cfg)
    except SafeError as e:
        # Only local media failures are safe for automatic retry.
        if str(e) not in {"local_media_tool_failed", "render_validation_failed"}:
            raise
        row = store.get(post_id)
        attempts = row["attempts"] + 1
        seconds = cfg["retry"]["base_seconds"] * (2 ** (attempts - 1))
        next_at = (dt.datetime.now(UTC) + dt.timedelta(seconds=seconds)).isoformat() if attempts < cfg["retry"]["max_attempts"] else None
        store.db.execute("UPDATE posts SET state='failed',attempts=?,next_attempt=?,error_code=?,updated_at=? WHERE id=?", (attempts, next_at, str(e), now(), post_id))
        store.event(post_id, "render_failed")
        store.db.commit()
        return {"id": post_id, "state": "failed", "error_code": str(e), "public": False}
