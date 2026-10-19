#!/usr/bin/env python3
"""Drive the official gh device flow without printing codes or storing transcripts.

The owner must authorize GitHub CLI in the browser. The short-lived code is passed
only through the Mac clipboard, never command-line arguments, files or logs.
"""
import hmac
import json
import os
import re
import select
import subprocess
import time


def announce(phase, **fields):
    print(json.dumps({"phase": phase, **fields}), flush=True)


def clipboard_read():
    return subprocess.run(["/usr/bin/pbpaste"], capture_output=True, timeout=5, check=True).stdout.strip()


def login():
    process = subprocess.Popen(["/usr/local/bin/gh", "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=dict(os.environ, GH_BROWSER="/usr/bin/true", GH_PROMPT_DISABLED="1"))
    master = process.stdout.fileno()
    announce("official_cli_started")
    buffer = ""
    device_code = None
    deadline = time.monotonic() + 900
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([master], [], [], 0.25)
            if readable:
                try:
                    data = os.read(master, 8192)
                except OSError:
                    data = b""
                if data:
                    buffer = (buffer + data.decode("utf-8", errors="replace"))[-20000:]
                    plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", buffer)
                    if "one-time code" in plain and device_code is None:
                        match = re.search(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b", plain)
                        if match:
                            device_code = match.group(1).encode()
                            subprocess.run(["/usr/bin/pbcopy"], input=device_code, capture_output=True, timeout=5, check=True)
                            if not hmac.compare_digest(clipboard_read(), device_code):
                                raise RuntimeError()
                            announce("code_copied_to_mac_clipboard")
                            announce("waiting_for_owner_browser_authorization")
            if process.poll() is not None:
                if process.returncode != 0:
                    announce("authorization_not_completed")
                    return 1
                result = subprocess.run(["/usr/local/bin/gh", "auth", "setup-git", "--hostname", "github.com"], capture_output=True, timeout=30)
                announce("authorized", git_helper_configured=result.returncode == 0)
                return result.returncode
        announce("authorization_expired")
        return 1
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        process.stdout.close()
        if device_code is not None:
            try:
                if hmac.compare_digest(clipboard_read(), device_code):
                    subprocess.run(["/usr/bin/pbcopy"], input=b"", capture_output=True, timeout=5)
            except Exception:
                pass


if __name__ == "__main__":
    try:
        raise SystemExit(login())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception:
        announce("local_authorization_setup_failed")
        raise SystemExit(1)
