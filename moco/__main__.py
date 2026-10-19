import argparse
import getpass
import json
import sys
from pathlib import Path

from .accounts import AccountAPI, Secrets
from .core import ROOT, SafeError, Store, atomic_json, canonical, settings
from .engine import analysis, execute, render_with_retry, tick
from .github import GitHub


def main():
    parser = argparse.ArgumentParser(description="MOCO local draft automation (public posting locked)")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("draft"); p.add_argument("--platform", choices=["youtube", "instagram", "threads"], required=True); p.add_argument("--topic", required=True)
    for cmd in ["render", "review"]:
        p = sub.add_parser(cmd); p.add_argument("id")
    p = sub.add_parser("revise"); p.add_argument("id"); p.add_argument("--file", required=True)
    p = sub.add_parser("approve"); p.add_argument("id"); p.add_argument("--digest", required=True); p.add_argument("--owner-confirmed", action="store_true", required=True)
    p = sub.add_parser("schedule"); p.add_argument("id"); p.add_argument("--at", required=True)
    p = sub.add_parser("tick"); p.add_argument("--github", action="store_true")
    sub.add_parser("status"); sub.add_parser("analyze"); sub.add_parser("stop")
    p = sub.add_parser("resume"); p.add_argument("--owner-confirmed", action="store_true", required=True)
    sub.add_parser("github-check")
    p = sub.add_parser("account"); p.add_argument("platform", choices=["youtube", "instagram", "threads"])
    p = sub.add_parser("collect"); p.add_argument("platform", choices=["youtube", "instagram", "threads"]); p.add_argument("--remote-id", required=True)
    p = sub.add_parser("secret-set"); p.add_argument("platform", choices=["instagram", "threads"])
    p = sub.add_parser("secret-import"); p.add_argument("platform", choices=["instagram", "threads"])
    p = sub.add_parser("auth-youtube"); p.add_argument("--client-file", required=True)
    args = parser.parse_args()
    cfg, store = settings(), Store()
    try:
        if args.action == "draft":
            with store.lock():
                result = execute(store, cfg, {"action": "draft", "platform": args.platform, "topic": args.topic})
        elif args.action == "render":
            with store.lock():
                result = render_with_retry(store, cfg, args.id)
        elif args.action == "review":
            result = {"id": args.id, "review_digest": store.bundle_digest(args.id), "assets": str(store.asset_dir(args.id)), "public": False}
        elif args.action == "revise":
            try:
                path = Path(args.file)
                if path.stat().st_size > 50000:
                    raise SafeError("draft_too_large")
                content = json.loads(path.read_text())
            except (OSError, ValueError):
                raise SafeError("draft_file_invalid") from None
            with store.lock():
                store.revise(args.id, content)
            result = {"id": args.id, "state": "awaiting_review", "public": False}
        elif args.action in {"approve", "schedule"}:
            with store.lock():
                if args.action == "approve":
                    store.approve(args.id, args.digest)
                else:
                    store.schedule(args.id, args.at)
                result = {"id": args.id, "state": store.get(args.id)["state"], "public": False}
        elif args.action == "tick":
            result = tick(store, cfg, args.github)
        elif args.action == "resume":
            with store.lock():
                store.resume()
            result = {"stopped": False, "public": False}
        elif args.action == "stop":
            # Stop never waits for a worker lock. In-flight local rendering can finish.
            store.stop(); result = {"stopped": True, "public": False}
        elif args.action == "status":
            result = {"mode": cfg["mode"], "stopped": store.stopped, "posts": store.summary(), "public": False}
        elif args.action == "analyze":
            with store.lock():
                result = analysis(store)
        elif args.action == "github-check":
            result = GitHub(cfg["github"]).identity()
        elif args.action == "account":
            result = AccountAPI(args.platform, cfg).identity()
            atomic_json(store.var / f"reports/account-{args.platform}.json", result)
        elif args.action == "collect":
            with store.lock():
                result = AccountAPI(args.platform, cfg).measured_metrics(args.remote_id)
                # Existing external posts are registered only after remote ownership verification.
                row = store.add(args.platform, {"existing_remote_id": args.remote_id})
                store.db.execute("UPDATE posts SET state='published',remote_id=?,remote_url=? WHERE id=?", (args.remote_id, result["remote_url"], row["id"]))
                store.db.execute("INSERT INTO metrics(post_id,source,collected_at,payload) VALUES(?,?,?,?)", (row["id"], result["source"], result["collected_at"], canonical(result)))
                store.db.commit()
                atomic_json(store.var / "reports" / f"metrics-{row['id']}.json", result)
        elif args.action == "secret-import":
            from .token_import import receive_token
            result = receive_token(args.platform)
            atomic_json(store.var / "reports" / ("token-import-" + args.platform + ".json"), result)
        elif args.action == "secret-set":
            secret = getpass.getpass("MacのKeychainに保存するアクセストークン（非表示）: ")
            if not secret.strip():
                raise SafeError("empty_secret_rejected")
            Secrets().set(args.platform, secret)
            result = {"status": "stored_in_macos_keychain"}
        elif args.action == "auth-youtube":
            from .oauth import youtube_authorize
            result = youtube_authorize(args.client_file)
        else:
            raise SafeError("command_action_not_allowed")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        main()
    except SafeError as e:
        print(json.dumps({"status": "error", "error_code": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        # Tracebacks can include URLs/tokens. Investigate locally with sanitized diagnostics.
        print('{"status":"error","error_code":"unexpected_local_error"}', file=sys.stderr)
        sys.exit(1)
