#!/usr/bin/env python3
"""
Stage 2: Video Renderer
Takes a script JSON from Stage 1 and generates a video via MoneyPrinterTurbo API.

Prerequisites:
    - MoneyPrinterTurbo running: cd MoneyPrinterTurbo && uv run python main.py
    - Default API: http://127.0.0.1:8080

Usage:
    python stage2_video_renderer.py --script script.json --output video.mp4
    python stage2_video_renderer.py --script script.json --api http://192.168.1.50:8080 --output video.mp4
    python stage2_video_renderer.py --script script.json --dry-run  # validate only, no API call

Configuration via environment variables or --config:
    MPT_API_URL=http://127.0.0.1:8080
    MPT_VOICE_NAME=en-US-JennyNeural
    MPT_PEXELS_API_KEY=your_key
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ─── Defaults ─────────────────────────────────────────────────────────────

DEFAULT_API_URL = os.environ.get("MPT_API_URL", "http://127.0.0.1:8080")
DEFAULT_VOICE = os.environ.get("MPT_VOICE_NAME", "en-US-JennyNeural")
DEFAULT_VOICE_RATE = float(os.environ.get("MPT_VOICE_RATE", "1.0"))
POLL_INTERVAL = 5  # seconds
MAX_WAIT = 600     # 10 minutes


def _get_requests():
    """Lazy-load requests to avoid import errors when only using build_video_request."""
    try:
        import requests as _requests
        return _requests
    except ImportError:
        print("ERROR: 'requests' library required. Install: pip install requests")
        sys.exit(1)


def build_video_request(script: dict, config: dict | None = None) -> dict:
    """
    Build a MoneyPrinterTurbo TaskVideoRequest from a Stage 1 script.

    script format (from Stage 1):
        {
            "video_subject": "...",
            "video_script": "...",
            "video_terms": ["kw1", "kw2", ...],
            "metadata": {...}
        }

    Returns a dict matching VideoParams schema for POST /videos.
    """
    cfg = config or {}

    body = {
        "video_subject": script.get("video_subject", "AI News"),
        "video_script": script.get("video_script", ""),
        "video_terms": script.get("video_terms", ["ai", "technology"]),
        "video_aspect": cfg.get("video_aspect", "9:16"),  # portrait for Shorts
        "video_concat_mode": cfg.get("video_concat_mode", "random"),
        "video_clip_duration": cfg.get("video_clip_duration", 5),
        "video_count": cfg.get("video_count", 1),
        "video_source": cfg.get("video_source", "pexels"),
        "voice_name": cfg.get("voice_name", DEFAULT_VOICE),
        "voice_rate": cfg.get("voice_rate", DEFAULT_VOICE_RATE),
        "voice_volume": cfg.get("voice_volume", 1.0),
        "bgm_type": cfg.get("bgm_type", "random"),
        "bgm_volume": cfg.get("bgm_volume", 0.15),
        "subtitle_enabled": cfg.get("subtitle_enabled", True),
        "font_size": cfg.get("font_size", 54),
        "text_fore_color": cfg.get("text_fore_color", "#FFFFFF"),
        "stroke_color": cfg.get("stroke_color", "#000000"),
        "stroke_width": cfg.get("stroke_width", 1.5),
        "n_threads": cfg.get("n_threads", 2),
    }

    return body


def create_video_task(api_url: str, body: dict) -> dict:
    """POST /videos to MoneyPrinterTurbo. Returns task info with task_id."""
    requests = _get_requests()
    url = f"{api_url.rstrip('/')}/videos"
    resp = requests.post(url, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_task_status(api_url: str, task_id: str) -> dict:
    """GET /tasks/{task_id} to check progress."""
    requests = _get_requests()
    url = f"{api_url.rstrip('/')}/tasks/{task_id}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    return result.get("data", result)


def wait_for_completion(
    api_url: str,
    task_id: str,
    poll_interval: int = POLL_INTERVAL,
    max_wait: int = MAX_WAIT,
) -> dict:
    """Poll task until complete or timeout."""
    requests = _get_requests()
    start = time.time()
    last_progress = -1

    while (time.time() - start) < max_wait:
        try:
            task = get_task_status(api_url, task_id)
        except requests.RequestException as e:
            print(f"  ⚠️  Poll error (will retry): {e}")
            time.sleep(poll_interval)
            continue

        state = task.get("state", -1)
        progress = task.get("progress", 0)

        if progress != last_progress:
            print(f"  Progress: {progress}%")
            last_progress = progress

        # state: 0=pending, 1=processing, 2=completed, -1=failed
        if state == 2:
            print(f"  ✅ Video complete in {time.time() - start:.0f}s")
            return task
        elif state == -1:
            error_msg = task.get("message", "Unknown error")
            raise RuntimeError(f"Video generation failed: {error_msg}")

        time.sleep(poll_interval)

    raise TimeoutError(f"Video generation timed out after {max_wait}s")


def download_video(task: dict, api_url: str, output_path: str) -> str:
    """Download the generated video from the task result."""
    requests = _get_requests()
    videos = task.get("videos", [])
    combined = task.get("combined_videos", [])

    video_url = None
    if combined:
        video_url = combined[0]
    elif videos:
        video_url = videos[0]

    if not video_url:
        raise ValueError("No video URL in task result")

    # Make sure URL is absolute
    if video_url.startswith("/"):
        video_url = f"{api_url.rstrip('/')}{video_url}"

    print(f"  Downloading: {video_url}")
    resp = requests.get(video_url, stream=True, timeout=120)
    resp.raise_for_status()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Downloaded: {output_path} ({size_mb:.1f} MB)")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate a short-form video via MoneyPrinterTurbo API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --script script.json --output video.mp4
  %(prog)s --script script.json --api http://mpt.local:8080 --output video.mp4
  %(prog)s --script script.json --dry-run
  %(prog)s --script script.json --config config.json --output video.mp4
        """,
    )
    parser.add_argument("--script", "-s", required=True, help="Stage 1 script JSON file")
    parser.add_argument("--output", "-o", default="output.mp4", help="Output video file path")
    parser.add_argument("--api", default=DEFAULT_API_URL, help=f"MoneyPrinterTurbo API URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--config", "-c", help="Optional config JSON (voice, style overrides)")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print request body; don't call API")
    parser.add_argument("--poll-interval", type=int, default=POLL_INTERVAL, help=f"Status poll interval in seconds (default: {POLL_INTERVAL})")
    parser.add_argument("--max-wait", type=int, default=MAX_WAIT, help=f"Max wait time in seconds (default: {MAX_WAIT})")
    args = parser.parse_args()

    # Load script
    with open(args.script) as f:
        script = json.load(f)

    # Load optional config
    config = {}
    if args.config:
        with open(args.config) as f:
            config = json.load(f)

    # Build request
    body = build_video_request(script, config)

    if args.dry_run:
        print("=== Dry Run — Request Body ===")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        print(f"\nTarget API: {args.api}/videos")
        print("Dry run complete. No API call made.")
        return

    # Check API health
    try:
        requests = _get_requests()
        health = requests.get(f"{args.api.rstrip('/')}/tasks?page=1&page_size=1", timeout=10)
        print(f"✅ API reachable: {args.api}")
    except Exception:
        print(f"❌ Cannot reach MoneyPrinterTurbo at {args.api}")
        print("   Start it: cd MoneyPrinterTurbo && uv run python main.py")
        sys.exit(1)

    # Create video task
    print(f"📹 Creating video: {body['video_subject']}")
    try:
        task_response = create_video_task(args.api, body)
    except Exception as e:
        print(f"❌ API error: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"   Response: {e.response.text[:500]}")
        sys.exit(1)

    task_data = task_response.get("data", task_response)
    task_id = task_data.get("task_id")
    print(f"   Task ID: {task_id}")

    # Wait for completion
    print(f"⏳ Waiting for video generation (polling every {args.poll_interval}s)...")
    try:
        final_task = wait_for_completion(args.api, task_id, args.poll_interval, args.max_wait)
    except (TimeoutError, RuntimeError) as e:
        print(f"❌ {e}")
        print(f"   Task ID: {task_id} — you can check it later: GET {args.api}/tasks/{task_id}")
        sys.exit(1)

    # Download
    video_path = download_video(final_task, args.api, args.output)

    # Write manifest
    manifest_path = args.output.replace(".mp4", ".manifest.json")
    manifest = {
        "task_id": task_id,
        "video_path": os.path.abspath(video_path),
        "script": script.get("video_subject", ""),
        "duration_from_script": script.get("metadata", {}).get("estimated_duration_seconds"),
        "api_url": args.api,
        "generated_at": script.get("metadata", {}).get("generated_at"),
        "file_size_bytes": os.path.getsize(video_path),
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✅ Done! Video: {video_path}")
    print(f"   Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
