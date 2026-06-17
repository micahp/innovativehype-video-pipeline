#!/usr/bin/env python3
"""
Stage 4: Pipeline Orchestrator
Wires Stage 1 → Stage 2 → Stage 3 into a single automated pipeline.

Usage:
    # Full pipeline: news → script → video → distribute
    python pipeline_video.py --newsletter newsletter.md --output-dir ./out

    # From existing script
    python pipeline_video.py --script script.json --output-dir ./out

    # Single topic, full pipeline
    python pipeline_video.py --topic "GPT-5 released with agent capabilities" --output-dir ./out

    # Skip distribution (just generate video)
    python pipeline_video.py --topic "..." --skip-distribute

    # Dry run all stages
    python pipeline_video.py --topic "..." --dry-run

Environment variables:
    MPT_API_URL          MoneyPrinterTurbo API URL (default: http://127.0.0.1:8080)
    MPT_VOICE_NAME       TTS voice (default: en-US-JennyNeural)
    YOUTUBE_CREDENTIALS_FILE  Path to Google OAuth client secret
    INSTAGRAM_ACCESS_TOKEN    Instagram Graph API token
    INSTAGRAM_IG_USER_ID      Instagram user ID
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent.resolve()


def run_stage(name: str, cmd: list[str], dry_run: bool = False) -> int:
    """Run a pipeline stage. Returns exit code."""
    print(f"\n{'='*60}")
    print(f"▶  STAGE: {name}")
    print(f"{'='*60}")
    print(f"   Command: {' '.join(cmd)}")

    if dry_run:
        print("   [DRY RUN] Skipping execution.")
        return 0

    start = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - start

    if result.returncode == 0:
        print(f"   ✅ Completed in {elapsed:.1f}s")
    else:
        print(f"   ❌ Failed with exit code {result.returncode} ({elapsed:.1f}s)")

    return result.returncode


def run_pipeline(
    *,
    topic: str | None = None,
    newsletter: str | None = None,
    script_file: str | None = None,
    output_dir: str = "./pipeline_output",
    mpt_api: str | None = None,
    mpt_config: str | None = None,
    youtube_privacy: str = "public",
    skip_distribute: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Execute the full pipeline.

    Flow: topic/newsletter → script.json → video.mp4 → distribution
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    script_path = os.path.join(output_dir, f"script_{timestamp}.json")
    video_path = os.path.join(output_dir, f"video_{timestamp}.mp4")
    manifest_path = video_path.replace(".mp4", ".manifest.json")
    result_path = os.path.join(output_dir, f"distribution_{timestamp}.json")
    log_path = os.path.join(output_dir, f"pipeline_{timestamp}.log")

    results = {
        "pipeline_started": datetime.now(timezone.utc).isoformat(),
        "output_dir": os.path.abspath(output_dir),
        "stages": {},
    }

    # ─── Stage 1: Script Generation ───────────────────────────────────
    if script_file:
        # Use existing script, copy to output dir
        print(f"📝 Using existing script: {script_file}")
        import shutil
        shutil.copy(script_file, script_path)
        results["stages"]["stage1_script"] = {"status": "skipped", "script": script_path}
    else:
        stage1_cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "stage1_script_generator.py"),
            "--output", script_path,
            "--max-duration", "55",
        ]
        if topic:
            stage1_cmd += ["--topic", topic]
        elif newsletter:
            stage1_cmd += ["--newsletter", newsletter]
        else:
            print("❌ Must provide --topic, --newsletter, or --script")
            sys.exit(1)

        rc = run_stage("Script Generation", stage1_cmd, dry_run)
        results["stages"]["stage1_script"] = {"status": "ok" if rc == 0 else "failed", "script": script_path}
        if rc != 0:
            return results

    # Load script for metadata
    if dry_run or os.path.exists(script_path):
        if os.path.exists(script_path):
            with open(script_path) as f:
                script_data = json.load(f)
        else:
            script_data = {"video_subject": topic or "Unknown", "video_terms": [], "metadata": {}}

        results["script"] = {
            "subject": script_data.get("video_subject", ""),
            "duration_est": script_data.get("metadata", {}).get("estimated_duration_seconds"),
            "keywords": script_data.get("video_terms", []),
        }

    # ─── Stage 2: Video Rendering ─────────────────────────────────────
    stage2_cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "stage2_video_renderer.py"),
        "--script", script_path,
        "--output", video_path,
    ]
    if mpt_api:
        stage2_cmd += ["--api", mpt_api]
    if mpt_config:
        stage2_cmd += ["--config", mpt_config]
    if dry_run:
        stage2_cmd.append("--dry-run")

    rc = run_stage("Video Rendering (MoneyPrinterTurbo)", stage2_cmd, dry_run)
    results["stages"]["stage2_render"] = {
        "status": "ok" if rc == 0 else "failed",
        "video": video_path,
        "manifest": manifest_path,
    }
    if rc != 0 and not dry_run:
        return results

    # ─── Stage 3: Distribution ────────────────────────────────────────
    if skip_distribute:
        print("\n⏭️  Skipping distribution (--skip-distribute)")
        results["stages"]["stage3_distribute"] = {"status": "skipped"}
    else:
        stage3_cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "stage3_distributor.py"),
            "--video", video_path,
            "--manifest", manifest_path,
            "--platform", "youtube",
            "--privacy", youtube_privacy,
            "--output", result_path,
        ]

        rc = run_stage("Distribution (YouTube Shorts)", stage3_cmd, dry_run)
        results["stages"]["stage3_distribute"] = {
            "status": "ok" if rc == 0 else "failed",
            "result": result_path,
        }

    # ─── Summary ──────────────────────────────────────────────────────
    results["pipeline_completed"] = datetime.now(timezone.utc).isoformat()

    # Write pipeline log
    with open(log_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print("🏁 PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"   Script:   {script_path}")
    print(f"   Video:    {video_path}")
    print(f"   Manifest: {manifest_path}")
    print(f"   Results:  {result_path}")
    print(f"   Log:      {log_path}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Automated short-form video pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --topic "OpenAI releases GPT-5" --output-dir ./out
  %(prog)s --newsletter newsletter.md --output-dir ./out
  %(prog)s --script script.json --output-dir ./out
  %(prog)s --topic "..." --skip-distribute --dry-run
  %(prog)s --topic "..." --mpt-api http://mpt.local:8080 --output-dir ./out
        """,
    )
    # Input
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--topic", "-t", help="Single topic/headline")
    input_group.add_argument("--newsletter", "-n", help="Markdown newsletter file")
    input_group.add_argument("--script", "-s", help="Pre-generated script JSON")

    # Output
    parser.add_argument("--output-dir", "-o", default="./pipeline_output",
                        help="Output directory (default: ./pipeline_output)")

    # MoneyPrinterTurbo
    parser.add_argument("--mpt-api", default=os.environ.get("MPT_API_URL"),
                        help="MoneyPrinterTurbo API URL")
    parser.add_argument("--mpt-config", help="MPT config JSON (voice, style overrides)")

    # Distribution
    parser.add_argument("--skip-distribute", action="store_true",
                        help="Skip uploading to platforms")
    parser.add_argument("--youtube-privacy", default="unlisted",
                        choices=["public", "unlisted", "private"],
                        help="YouTube privacy status (default: unlisted for testing)")

    # Debug
    parser.add_argument("--dry-run", action="store_true",
                        help="Dry run — validate without API calls")

    args = parser.parse_args()

    results = run_pipeline(
        topic=args.topic,
        newsletter=args.newsletter,
        script_file=args.script,
        output_dir=args.output_dir,
        mpt_api=args.mpt_api,
        mpt_config=args.mpt_config,
        youtube_privacy=args.youtube_privacy,
        skip_distribute=args.skip_distribute,
        dry_run=args.dry_run,
    )

    # Exit with error if any stage failed
    for stage_name, stage_info in results.get("stages", {}).items():
        if stage_info.get("status") == "failed":
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
