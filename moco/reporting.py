"""Report completed collection batches; never replay an uncertain GitHub POST."""
import datetime as dt
import json
import re

from .core import SafeError, atomic_json, now
from .github import GitHub, REPOSITORY


def read_report(path):
    try:
        if path.stat().st_size > 100000:
            raise ValueError()
        result = json.loads(path.read_text())
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (OSError, ValueError):
        raise SafeError("metrics_report_file_invalid") from None


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.isoformat()
    except (TypeError, ValueError):
        raise SafeError("metrics_report_timestamp_invalid") from None


def public_measurements(store, cfg):
    """Allowlist public YouTube counters, not arbitrary fields or private insights."""
    result = []
    rows = store.db.execute('''SELECT payload FROM metrics WHERE n IN
        (SELECT MAX(n) FROM metrics GROUP BY post_id) ORDER BY n''').fetchall()
    target = cfg["accounts"]["youtube"]
    if not target.get("owner_confirmed") or not target.get("account_id"):
        return result
    for row in rows:
        data = json.loads(row["payload"])
        video = data.get("remote_id", "")
        if (data.get("platform") != "youtube" or data.get("visibility") != "public"
                or data.get("source") != "youtube_data_api.videos.list"
                or str(data.get("account_id")) != str(target["account_id"])
                or not isinstance(video, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video)):
            continue
        url = data.get("remote_url")
        if url not in {"https://www.youtube.com/shorts/" + video,
                       "https://www.youtube.com/watch?v=" + video}:
            continue
        counts = {k: data.get("metrics", {}).get(k) for k in ["views", "likes", "comments"]}
        if any(v is not None and (type(v) is not int or v < 0) for v in counts.values()):
            continue
        result.append({"remote_id": video, "public_url": url,
            "collected_at": timestamp(data.get("collected_at")),
            "source": "youtube_data_api.videos.list", "metrics": counts})
    return result


def report_metrics_checkpoint(store, cfg, client=None):
    if store.stopped:
        return {"status": "stopped", "public": False}
    destination = cfg["github"].get("metrics_report_issue")
    checkpoint = store.var / "reports/metrics-collection.json"
    if not destination or not checkpoint.exists():
        return {"status": "disabled", "public": False}
    try:
        if (not isinstance(destination, dict) or set(destination) != {"number", "id"}
                or any(type(v) is not int or v <= 0 for v in destination.values())):
            raise SafeError("metrics_report_destination_invalid")
        outbox_path = store.var / "reports/github-metrics-outbox.json"
        outbox = read_report(outbox_path) if outbox_path.exists() else None
        batch = read_report(checkpoint)
        if batch.get("status") not in {"completed", "partial_failure"}:
            return {"status": "waiting_for_collection", "public": False}
        run_key = timestamp(batch.get("last_attempt_at"))
        if outbox and outbox.get("destination") != destination:
            raise SafeError("metrics_report_destination_changed")
        if outbox and outbox.get("status") == "reported" and outbox.get("run_key") == run_key:
            return {"status": "reported", "comment_id": outbox["comment_id"], "public": False}
        if not outbox or outbox.get("status") == "reported":
            count = batch.get("updated_posts")
            if type(count) is not int or count < 0 or not isinstance(batch.get("failures"), list):
                raise SafeError("metrics_report_batch_invalid")
            payload = {"generated_at": now(), "sns_posts_created": 0,
                "collection": {"status": batch["status"], "started_at": run_key,
                    "finished_at": timestamp(batch.get("finished_at")),
                    "updated_posts": count, "failure_count": len(batch["failures"]),
                    "next_due_at": timestamp(batch.get("next_due_at"))},
                "latest_public_youtube_measurements": public_measurements(store, cfg),
                "note": "未取得はnull。各実測の取得時刻を参照。詳細Insightsや認証情報は含めない。"}
            outbox = {"run_key": run_key, "destination": destination, "status": "prepared",
                "marker": "<!-- moco-metrics-report:" + run_key + " -->", "payload": payload}
            atomic_json(outbox_path, outbox)
        client = client or GitHub(cfg["github"], store.root)
        issue = client.call("GET", f"/repos/{REPOSITORY}/issues/{destination['number']}")
        if (issue.get("id") != destination["id"] or "pull_request" in issue
                or issue.get("state") != "open"
                or issue.get("user", {}).get("id") not in cfg["github"]["trusted_actor_ids"]):
            raise SafeError("metrics_report_destination_not_trusted")
        for comment in client.comments(destination["number"]):
            if (outbox["marker"] in (comment.get("body") or "")
                    and comment.get("user", {}).get("id") in cfg["github"]["trusted_actor_ids"]):
                outbox.update(status="reported", comment_id=comment["id"])
                atomic_json(outbox_path, outbox)
                return {"status": "reported", "comment_id": comment["id"], "public": False}
        if outbox["status"] != "prepared":
            # Unknown POST outcome: reconcile by GET; never create another comment blindly.
            return {"status": "verification_required", "public": False}
        outbox["status"] = "posting"
        atomic_json(outbox_path, outbox)
        body = (outbox["marker"] + "\nMacの実測更新レポート（新規SNS公開なし）\n```json\n"
                + json.dumps(outbox["payload"], ensure_ascii=False, indent=2) + "\n```")
        response = client.call("POST", f"/repos/{REPOSITORY}/issues/{destination['number']}/comments", {"body": body})
        outbox.update(status="reported", comment_id=response["id"])
        atomic_json(outbox_path, outbox)
        return {"status": "reported", "comment_id": response["id"], "public": False}
    except SafeError as e:
        return {"status": "failed", "error_code": str(e), "public": False}
    except Exception:
        return {"status": "failed", "error_code": "metrics_report_failed", "public": False}
