#!/usr/bin/env python3
"""Pin the authenticated operator's numeric ID after verifying repository write access."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from moco.core import SafeError, atomic_json, settings
from moco.github import GitHub, REPOSITORY

def configure_operator(root=ROOT, client=None):
    cfg = settings(root)
    info = (client or GitHub(cfg["github"], root)).identity()
    if info["repository"].lower() != REPOSITORY.lower() or not info["push"] or not info["issues_enabled"]:
        raise SafeError("authenticated_operator_with_repository_write_access_required")
    path = root / "config/local.json"
    if path.is_symlink():
        path = path.resolve(strict=True)
    data = json.loads(path.read_text()) if path.exists() else {}
    trusted = data.setdefault("github", {}).setdefault("trusted_actor_ids", [])
    if info["id"] not in trusted:
        trusted.append(info["id"])
    atomic_json(path, data)
    return {"status": "configured", "login": info["login"], "numeric_id_pinned": True}


if __name__ == "__main__":
    try:
        print(json.dumps(configure_operator(), ensure_ascii=False))
    except SafeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
