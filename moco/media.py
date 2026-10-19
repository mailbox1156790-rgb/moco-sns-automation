import hashlib
import json
import os
from pathlib import Path
import subprocess

from .core import ROOT, SafeError, atomic_json, now


def run(args, **kwargs):
    try:
        return subprocess.run(args, check=True, capture_output=True, timeout=300, **kwargs)
    except (OSError, subprocess.SubprocessError):
        # Never forward tool stderr or input paths/text to logs.
        raise SafeError("local_media_tool_failed") from None


def native(root=ROOT):
    binary = root / "var/bin/moco-native"
    source = root / "scripts/native.swift"
    if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
        binary.parent.mkdir(parents=True, exist_ok=True)
        # Clang PCH embeds the cache's absolute path. Runtime releases and the
        # checkout share var via symlinks, so use one canonical cache directory.
        # Keep the old alias-dependent cache intact for recovery.
        cache = (root / "var/swift-cache-canonical").resolve()
        cache.mkdir(exist_ok=True)
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(cache), SWIFT_MODULECACHE_PATH=str(cache))
        temporary = binary.with_suffix(".tmp")
        run(["/usr/bin/swiftc", "-O", "-module-cache-path", str(cache), str(source), "-o", str(temporary)], env=env)
        temporary.replace(binary)
    return binary


def native_call(mode, payload, root=ROOT):
    return run([str(native(root)), mode], input=json.dumps(payload).encode()).stdout


def render(store, post_id, cfg):
    if store.stopped:
        raise SafeError("Stopped. Resume locally first.")
    row = store.get(post_id)
    if row["state"] not in {"awaiting_review", "failed"}:
        raise SafeError("Rendering an approved draft is locked. Create a new draft for revisions.")
    data = json.loads(row["content"])
    assets = store.asset_dir(post_id)
    atomic_json(assets / "draft.json", data)
    for n, title in enumerate(data["slides"]):
        native_call("card", {"text": title, "output": str(assets / f"slide-{n}.png")}, store.root)
    (assets / "cover.png").write_bytes((assets / "slide-0.png").read_bytes())
    (assets / "narration.txt").write_text("\n".join(data["script"]))
    run(["/usr/bin/say", "-v", cfg["render"]["voice"], "-f", str(assets / "narration.txt"), "-o", str(assets / "voice.aiff")])
    result = run(["/usr/local/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(assets / "voice.aiff")])
    try:
        measured_duration = float(json.loads(result.stdout)["format"]["duration"])
        if measured_duration <= 0:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise SafeError("local_media_tool_failed") from None
    duration = max(12.0, measured_duration + 1.5)
    slide_duration = duration / len(data["slides"])
    lines = []
    for n in range(len(data["slides"])):
        lines += [f"file 'slide-{n}.png'", f"duration {slide_duration:.4f}"]
    lines += [f"file 'slide-{len(data['slides']) - 1}.png'"]
    (assets / "slides.txt").write_text("\n".join(lines) + "\n")
    run(["/usr/local/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "1", "-i", str(assets / "slides.txt"),
         "-i", str(assets / "voice.aiff"), "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-af", "apad", "-t", str(duration), "-movflags", "+faststart", str(assets / "video.mp4")])
    info = json.loads(run(["/usr/local/bin/ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(assets / "video.mp4")]).stdout)
    video = next((x for x in info["streams"] if x["codec_type"] == "video"), None)
    audio = next((x for x in info["streams"] if x["codec_type"] == "audio"), None)
    if not video or video["width"] != 1080 or video["height"] != 1920 or video["codec_name"] != "h264" or not audio:
        raise SafeError("render_validation_failed")
    store.db.execute("UPDATE posts SET state='awaiting_review',error_code=NULL,next_attempt=NULL,updated_at=? WHERE id=?", (now(), post_id))
    store.event(post_id, "local_media_verified")
    store.db.commit()
    receipt = {"id": post_id, "width": 1080, "height": 1920, "video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
               "duration_seconds": float(info["format"]["duration"]), "review_digest": store.bundle_digest(post_id), "public": False}
    atomic_json(assets / "render-receipt.json", receipt)
    return receipt
