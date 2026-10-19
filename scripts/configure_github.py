#!/usr/bin/env python3
"""Pin only the authenticated repository OWNER's numeric ID, never tokens."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from moco.core import SafeError, atomic_json, settings
from moco.github import GitHub, REPOSITORY

try:
    cfg = settings()
    info = GitHub(cfg["github"]).identity()
    if info["login"].lower() != REPOSITORY.split('/')[0].lower() or not info["push"] or not info["issues_enabled"]:
        raise SafeError("authenticated_repository_owner_with_issues_required")
    path = ROOT / "config/local.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data.setdefault("github", {})["trusted_actor_ids"] = [info["id"]]
    atomic_json(path, data)
    print(json.dumps({"status": "configured", "login": info["login"], "numeric_id_pinned": True}, ensure_ascii=False))
except SafeError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
