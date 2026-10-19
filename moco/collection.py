"""Periodically refresh measurements for already registered, owned posts only."""
import datetime as dt
import json

from .accounts import AccountAPI
from .core import SafeError, atomic_json, canonical, now


def refresh_metrics(store, cfg, client_factory=AccountAPI):
    """Called while the worker holds its lock. Never creates or publishes posts."""
    job = cfg.get("metrics_collection", {})
    if not job.get("enabled", False):
        return {"status": "disabled", "public": False}
    if store.stopped:
        return {"status": "stopped", "public": False}
    interval = job.get("interval_seconds", 21600)
    limit = job.get("max_posts_per_run", 20)
    platforms = job.get("platforms", [])
    if (type(interval) is not int or not 3600 <= interval <= 604800
            or type(limit) is not int or not 1 <= limit <= 100
            or not isinstance(platforms, list) or not platforms
            or any(not isinstance(p, str) or p not in {"youtube", "instagram", "threads"} for p in platforms)):
        raise SafeError("metrics_collection_settings_invalid")
    checkpoint = store.var / "reports/metrics-collection.json"
    current = dt.datetime.fromisoformat(now())
    if checkpoint.exists():
        try:
            previous = json.loads(checkpoint.read_text())
            last = dt.datetime.fromisoformat(previous["last_attempt_at"])
            if last.tzinfo is None:
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            raise SafeError("metrics_collection_checkpoint_invalid") from None
        due = last + dt.timedelta(seconds=interval)
        if current < due:
            return {"status": "waiting", "next_due_at": due.isoformat(), "public": False}
    rows = store.db.execute('''SELECT p.id,p.platform,p.remote_id,MAX(m.collected_at) AS last_collected
        FROM posts p LEFT JOIN metrics m ON m.post_id=p.id
        WHERE p.state='published' AND p.remote_id IS NOT NULL
        GROUP BY p.id ORDER BY COALESCE(MAX(m.collected_at),''),p.id''').fetchall()
    rows = [r for r in rows if r["platform"] in platforms][:limit]
    result = {"status": "running", "last_attempt_at": current.isoformat(),
              "updated_posts": 0, "failures": [], "public": False}
    # Reserve before network work, so restart cannot repeatedly issue the same batch.
    atomic_json(checkpoint, result)
    clients, blocked = {}, {}
    for row in rows:
        platform = row["platform"]
        try:
            account = cfg["accounts"][platform]
            if not account.get("owner_confirmed") or not account.get("account_id"):
                raise SafeError("owner_confirmed_pinned_account_required")
            if platform in blocked:
                raise SafeError(blocked[platform])
            if platform not in clients:
                try:
                    clients[platform] = client_factory(platform, cfg)
                except SafeError as e:
                    blocked[platform] = str(e)
                    raise
            measurement = clients[platform].measured_metrics(row["remote_id"])
            if (measurement.get("platform") != platform
                    or measurement.get("remote_id") != row["remote_id"]
                    or str(measurement.get("account_id")) != str(account["account_id"])):
                raise SafeError("collected_measurement_identity_mismatch")
            store.db.execute("INSERT INTO metrics(post_id,source,collected_at,payload) VALUES(?,?,?,?)",
                (row["id"], measurement["source"], measurement["collected_at"], canonical(measurement)))
            store.db.commit()
            atomic_json(store.var / "reports" / ("metrics-" + row["id"] + ".json"), measurement)
            result["updated_posts"] += 1
        except SafeError as e:
            result["failures"].append({"id": row["id"], "error_code": str(e)})
        except Exception:
            result["failures"].append({"id": row["id"], "error_code": "metrics_collection_failed"})
    result["status"] = "completed" if not result["failures"] else "partial_failure"
    result["finished_at"] = now()
    result["next_due_at"] = (current + dt.timedelta(seconds=interval)).isoformat()
    atomic_json(checkpoint, result)
    return result
