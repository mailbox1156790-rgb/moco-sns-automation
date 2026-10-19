#!/usr/bin/env python3
"""Manage a per-user launchd agent; no system daemon or self-hosted Actions runner."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LABEL = "jp.moco.sns-automation"
parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["prepare", "start", "install", "stop", "status", "uninstall"])
parser.add_argument("--github", action="store_true", help="Poll trusted GitHub Issues as well as local draft schedules")
args = parser.parse_args()
var = ROOT / "var"
var.mkdir(mode=0o700, exist_ok=True)
local = var / (LABEL + ".plist")
installed = Path.home() / "Library/LaunchAgents" / local.name
domain = f"gui/{os.getuid()}"


def launch(*argv):
    return subprocess.run(["/bin/launchctl", *argv], capture_output=True, text=True)


if args.action in {"prepare", "start", "install"}:
    command = ["/usr/bin/python3", str(ROOT / "scripts/worker.py"), "tick"] + (["--github"] if args.github else [])
    payload = {"Label": LABEL, "ProgramArguments": command, "WorkingDirectory": str(ROOT),
        "RunAtLoad": True, "StartInterval": 120, "ProcessType": "Background",
        "EnvironmentVariables": {"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/local/bin:/usr/bin:/bin"},
        "StandardOutPath": str(var / "worker.stdout.log"), "StandardErrorPath": str(var / "worker.stderr.log")}
    local.write_bytes(plistlib.dumps(payload))
    local.chmod(0o600)
    if args.action == "install":
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(local.read_bytes()); installed.chmod(0o600)
    if args.action != "prepare":
        launch("bootout", domain + "/" + LABEL)
        response = launch("bootstrap", domain, str(installed if args.action == "install" else local))
        if response.returncode:
            print("launchd_start_failed", file=sys.stderr); sys.exit(1)
    print("prepared" if args.action == "prepare" else "started_github_draft_only" if args.github else "started_local_draft_only")
elif args.action in {"stop", "uninstall"}:
    # STOP blocks subsequent work even if launchd cannot be contacted.
    (var / "STOP").touch(mode=0o600)
    launch("bootout", domain + "/" + LABEL)
    if args.action == "uninstall":
        installed.unlink(missing_ok=True)
    print("stopped")
else:
    result = launch("print", domain + "/" + LABEL)
    # Avoid echoing environment variables or unexpected launchctl diagnostics.
    print("loaded" if result.returncode == 0 else "not_loaded")
