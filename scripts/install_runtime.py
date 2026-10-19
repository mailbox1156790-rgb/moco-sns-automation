#!/usr/bin/env python3
"""Deploy an explicit local source snapshot outside Documents for macOS launchd.

Does not pull GitHub code. Preserves source data before linking shared runtime data.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
BASE = Path.home() / "Library/Application Support/MocoSNS"
parser = argparse.ArgumentParser()
parser.add_argument("--github", action="store_true")
args = parser.parse_args()

files = sorted([p for folder in ["moco", "scripts"] for p in (SOURCE / folder).glob("*") if p.is_file() and p.suffix in {".py", ".swift"}])
files += [SOURCE / "config/settings.json"]
hasher = hashlib.sha256()
for p in files:
    hasher.update(str(p.relative_to(SOURCE)).encode()); hasher.update(p.read_bytes())
revision = hasher.hexdigest()
release = BASE / "releases" / revision[:16]
data = BASE / "data"
BASE.mkdir(parents=True, mode=0o700, exist_ok=True); BASE.chmod(0o700)
release.mkdir(parents=True, exist_ok=True)
data.mkdir(mode=0o700, exist_ok=True); data.chmod(0o700)

# Serialize installation against foreground/periodic tasks. Existing worker is stopped first.
subprocess.run(["/bin/launchctl", "bootout", f"gui/{__import__('os').getuid()}/jp.moco.sns-automation"], capture_output=True)
source_var = SOURCE / "var"
source_var.mkdir(exist_ok=True)
lock = (source_var / "worker.lock").open("a")
import fcntl
try:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("worker_busy_retry_install_later", file=sys.stderr); sys.exit(1)

try:
    for p in files:
        target = release / p.relative_to(SOURCE)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Preserve source times so unchanged Swift code keeps its existing helper.
        # Rewriting its mtime on every deployment needlessly rebuilds the binary.
        shutil.copy2(p, target)
    if source_var.resolve() != data.resolve():
        # Refuse to overwrite any previously installed data from a different checkout.
        if (data / "state.sqlite3").exists():
            print("existing_runtime_data_requires_manual_reconciliation", file=sys.stderr); sys.exit(1)
        old_db = source_var / "state.sqlite3"
        if old_db.exists():
            with sqlite3.connect(str(old_db)) as src, sqlite3.connect(str(data / "state.sqlite3")) as dst:
                src.backup(dst)
        for name in ["assets", "reports", "bin"]:
            if (source_var / name).is_dir():
                shutil.copytree(source_var / name, data / name, dirs_exist_ok=True)
        if (source_var / "STOP").exists():
            (data / "STOP").touch(mode=0o600)
        backups = SOURCE / "work"
        backups.mkdir(exist_ok=True)
        source_var.rename(backups / ("var-before-runtime-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")))
        source_var.symlink_to(data, target_is_directory=True)
    local = SOURCE / "config/local.json"
    shared_local = BASE / "local-settings.json"
    if local.exists() and not local.is_symlink():
        if shared_local.exists() and shared_local.read_bytes() != local.read_bytes():
            print("local_settings_conflict_requires_manual_reconciliation", file=sys.stderr); sys.exit(1)
        shutil.copyfile(local, shared_local); shared_local.chmod(0o600)
        backup_local = SOURCE / "work" / ("local-settings-before-runtime-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
        backup_local.parent.mkdir(exist_ok=True)
        local.rename(backup_local)
    if not shared_local.exists():
        shared_local.write_text("{}\n"); shared_local.chmod(0o600)
    if not local.is_symlink():
        local.symlink_to(shared_local)
    for path, target, is_dir in [(release / "var", data, True), (release / "config/local.json", shared_local, False)]:
        if not path.is_symlink():
            path.symlink_to(target, target_is_directory=is_dir)
    manifest = {"source_sha256": revision, "source_checkout": str(SOURCE), "release": str(release),
        "data": str(data), "mode": "draft_only", "github_polling": args.github, "deployed_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    (BASE / "deployment.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
finally:
    fcntl.flock(lock.fileno(), fcntl.LOCK_UN); lock.close()

command = [sys.executable, str(release / "scripts/service.py"), "install"] + (["--github"] if args.github else [])
response = subprocess.run(command, capture_output=True, text=True)
print(json.dumps({"installed": response.returncode == 0, "source_sha256": revision, "runtime": str(release), "github_polling": args.github, "public": False}, ensure_ascii=False, indent=2))
sys.exit(response.returncode)
