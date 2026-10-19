#!/usr/bin/env python3
import json
import platform
import shutil
import ssl
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
def version(exe, flag):
    path = shutil.which(exe)
    if not path:
        return {"installed": False}
    try:
        r = subprocess.run([path, flag], capture_output=True, text=True, timeout=10)
        return {"installed": True, "path": path, "version": (r.stdout or r.stderr).splitlines()[0]}
    except (OSError, subprocess.SubprocessError, IndexError):
        return {"installed": True, "version": "unavailable"}

report = {"os": "macOS " + platform.mac_ver()[0], "architecture": platform.machine(),
          "python": platform.python_version(), "tools": {x: version(x, flag) for x, flag in [("git", "--version"), ("gh", "--version"), ("ffmpeg", "-version"), ("ffprobe", "-version")]},
          "browsers": [str(p) for p in [Path('/Applications/Google Chrome.app'), Path('/Applications/Safari.app')] if p.exists()],
          "tls_certificate_verification": ssl.create_default_context().verify_mode == ssl.CERT_REQUIRED,
          "secrets_in_report": False}
print(json.dumps(report, ensure_ascii=False, indent=2))
