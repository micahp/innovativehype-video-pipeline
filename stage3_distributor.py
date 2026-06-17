#!/usr/bin/env python3
"""
Stage 3: Distribution
Uploads generated videos to YouTube Shorts (and optionally Instagram/TikTok).

YouTube Shorts:
    - Requires Google Cloud project with YouTube Data API v3 enabled
    - OAuth 2.0 credentials (desktop app type)
    - Videos under 60s in 9:16 aspect ratio auto-classify as Shorts

Instagram Reels:
    - Requires Facebook App with instagram_content_publish permission
    - Instagram Professional Account connected to a Facebook Page
    - Page Publishing Authorization (PPA)
    - Two-step: media container → publish
    - NOTE: App Review required; may take days to weeks

TikTok:
    - Requires TikTok developer account + approved app
    - Content Posting API with video.publish scope
    - NOTE: Highly restricted; may not be available to all developers

Setup:
    1. YouTube: https://console.cloud.google.com → Enable YouTube Data API v3
    2. Create OAuth 2.0 Client ID (Desktop app)
    3. Download credentials as client_secret.json
    4. First run will open browser for OAuth consent

Usage:
    python stage3_distributor.py --video video.mp4 --manifest video.manifest.json --platform youtube
    python stage3_distributor.py --video video.mp4 --title "GPT-5 Changes Everything" --platform youtube
    python stage3_distributor.py --video video.mp4 --platform all  # Attempt all platforms
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── YouTube ──────────────────────────────────────────────────────────────

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
YOUTUBE_CREDENTIALS_FILE = os.environ.get(
    "YOUTUBE_CREDENTIALS_FILE",
    os.path.expanduser("~/.hermes/youtube_client_secret.json"),
)
YOUTUBE_TOKEN_FILE = os.environ.get(
    "YOUTUBE_TOKEN_FILE",
    os.path.expanduser("~/.hermes/youtube_token.json"),
)

# ─── Instagram ────────────────────────────────────────────────────────────

INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_IG_USER_ID = os.environ.get("INSTAGRAM_IG_USER_ID", "")
INSTAGRAM_API_VERSION = "v22.0"


def ensure_youtube_deps():
    """Check for Google API client libraries."""
    try:
        import googleapiclient.discovery
        import googleapiclient.errors
        import google_auth_oauthlib.flow
        import google.auth.transport.requests
    except ImportError:
        print("ERROR: Google API client required.")
        print("  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
        return False
    return True


def get_youtube_credentials():
    """Get or refresh YouTube OAuth credentials."""
    import google_auth_oauthlib.flow
    import google.auth.transport.requests
    import pickle

    creds = None

    # Try loading from token file
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        with open(YOUTUBE_TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # Refresh or create new
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            if not os.path.exists(YOUTUBE_CREDENTIALS_FILE):
                print(f"❌ YouTube credentials not found at {YOUTUBE_CREDENTIALS_FILE}")
                print("   1. Go to https://console.cloud.google.com/apis/credentials")
                print("   2. Create OAuth 2.0 Client ID (Desktop app)")
                print("   3. Download JSON → save as ~/.hermes/youtube_client_secret.json")
                return None

            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_CREDENTIALS_FILE, YOUTUBE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save for next time
        os.makedirs(os.path.dirname(YOUTUBE_TOKEN_FILE), exist_ok=True)
        with open(YOUTUBE_TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return creds


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    category_id: str = "28",  # Science & Technology
    privacy_status: str = "public",
) -> dict:
    """
    Upload a video to YouTube. Videos under 60s with vertical aspect
    ratio auto-classify as Shorts. No special Shorts upload needed.

    Returns: dict with video_id, url
    """
    if not ensure_youtube_deps():
        return {"error": "Missing dependencies"}

    import googleapiclient.discovery
    import googleapiclient.errors
    from googleapiclient.http import MediaFileUpload

    creds = get_youtube_credentials()
    if not creds:
        return {"error": "Authentication failed"}

    youtube = googleapiclient.discovery.build(
        YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=creds
    )

    # Build hashtags from description/title
    if tags is None:
        tags = ["AI", "ArtificialIntelligence", "TechNews", "InnovativeHype"]

    # Ensure #shorts tag for Shorts discovery
    if "#shorts" not in description.lower():
        description = f"{description}\n\n#shorts #ai #technews"

    body = {
        "snippet": {
            "title": title[:100],  # YouTube title limit
            "description": description[:5000],
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    print(f"📤 Uploading to YouTube: {title}")
    print(f"   File: {video_path} ({os.path.getsize(video_path) / (1024*1024):.1f} MB)")

    media = MediaFileUpload(
        video_path,
        mimetype="video/*",
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"   Uploaded: {int(status.progress() * 100)}%")
        except googleapiclient.errors.HttpError as e:
            print(f"❌ YouTube API error: {e}")
            return {"error": str(e)}

    video_id = response["id"]
    url = f"https://www.youtube.com/shorts/{video_id}"
    print(f"✅ Published: {url}")

    return {
        "platform": "youtube",
        "video_id": video_id,
        "url": url,
        "title": title,
        "uploaded_at": datetime.now().isoformat(),
    }


def upload_to_instagram(
    video_path: str,
    caption: str,
) -> dict:
    """
    Upload a video to Instagram Reels via the Instagram Content Publishing API.

    Prerequisites (one-time setup):
        1. Instagram Professional Account (Business or Creator)
        2. Connected to a Facebook Page
        3. Facebook App with instagram_content_publish permission (requires App Review)
        4. Page Publishing Authorization (PPA)
        5. Long-lived access token

    The video must be hosted at a publicly accessible URL (not direct upload).
    """
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_IG_USER_ID:
        print("⚠️  Instagram: Not configured (missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_IG_USER_ID)")
        print("   See README.md for Instagram setup instructions.")
        return {"platform": "instagram", "status": "skipped", "reason": "not_configured"}

    # Step 1: Create media container
    # Video must be publicly accessible URL — this is a limitation
    print("⚠️  Instagram requires a publicly accessible video URL (not direct file upload).")
    print("   Upload video to a hosting service first, then pass --video-url instead.")
    return {"platform": "instagram", "status": "skipped", "reason": "requires_public_url"}


def upload_to_tiktok(
    video_path: str,
    title: str,
) -> dict:
    """
    Upload to TikTok via Content Posting API.

    NOTE: TikTok API access is highly restricted. Most developers cannot
    obtain the video.publish permission without being an approved partner.
    """
    print("⚠️  TikTok: Content Posting API requires approved developer account.")
    print("   Most developers cannot obtain video.publish permission.")
    print("   See: https://developers.tiktok.com/products/content-posting-api")
    return {"platform": "tiktok", "status": "skipped", "reason": "api_restricted"}


def load_manifest(manifest_path: str) -> dict:
    """Load manifest from Stage 2 output."""
    with open(manifest_path) as f:
        return json.load(f)


def build_metadata(manifest: dict, script: dict | None = None) -> dict:
    """Build title, description, tags from manifest and script metadata."""
    title = manifest.get("script", "AI News Update")

    # Hashtag-rich description
    description_lines = [
        title,
        "",
        "The latest in AI, tech, and innovation — curated by Innovative Hype.",
        "",
        "#AI #ArtificialIntelligence #TechNews #Innovation #FutureTech #MachineLearning",
    ]
    description = "\n".join(description_lines)

    tags = [
        "AI", "ArtificialIntelligence", "TechNews", "InnovativeHype",
        "FutureTech", "MachineLearning", "Technology",
    ]

    return {"title": title, "description": description, "tags": tags}


def main():
    parser = argparse.ArgumentParser(
        description="Distribute video to platforms (YouTube Shorts, Instagram, TikTok)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video video.mp4 --manifest video.manifest.json --platform youtube
  %(prog)s --video video.mp4 --title "GPT-5 Is Here" --platform youtube
  %(prog)s --video video.mp4 --platform all
  %(prog)s --video video.mp4 --platform youtube --privacy unlisted
        """,
    )
    parser.add_argument("--video", "-v", required=True, help="Video file to upload")
    parser.add_argument("--manifest", "-m", help="Manifest JSON from Stage 2")
    parser.add_argument("--platform", "-p", default="youtube",
                        choices=["youtube", "instagram", "tiktok", "all"],
                        help="Target platform (default: youtube)")
    parser.add_argument("--title", "-t", help="Video title (overrides manifest)")
    parser.add_argument("--description", "-d", help="Video description")
    parser.add_argument("--privacy", default="public",
                        choices=["public", "unlisted", "private"],
                        help="YouTube privacy status (default: public)")
    parser.add_argument("--tags", nargs="*", help="Video tags")
    parser.add_argument("--output", "-o", default="distribution_result.json",
                        help="Output JSON with upload results")
    args = parser.parse_args()

    # Validate video exists
    if not os.path.exists(args.video):
        print(f"❌ Video not found: {args.video}")
        sys.exit(1)

    # Load manifest if provided
    manifest = {}
    if args.manifest:
        manifest = load_manifest(args.manifest)

    # Build metadata
    meta = build_metadata(manifest)
    title = args.title or meta["title"]
    description = args.description or meta["description"]
    tags = args.tags or meta["tags"]

    results = []

    platforms = ["youtube", "instagram", "tiktok"] if args.platform == "all" else [args.platform]

    for platform in platforms:
        print(f"\n{'='*60}")
        print(f"📱 Platform: {platform.upper()}")
        print(f"{'='*60}")

        if platform == "youtube":
            result = upload_to_youtube(
                args.video, title, description, tags, privacy_status=args.privacy
            )
        elif platform == "instagram":
            result = upload_to_instagram(args.video, description)
        elif platform == "tiktok":
            result = upload_to_tiktok(args.video, title)

        results.append(result)

    # Write results
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n{'='*60}")
    print("📊 Distribution Summary")
    print(f"{'='*60}")
    for r in results:
        platform = r.get("platform", "unknown")
        if "video_id" in r:
            print(f"  ✅ {platform}: {r.get('url', '')}")
        elif r.get("status") == "skipped":
            print(f"  ⚠️  {platform}: Skipped — {r.get('reason', '')}")
        elif "error" in r:
            print(f"  ❌ {platform}: {r['error']}")
    print(f"\nResults saved: {args.output}")


if __name__ == "__main__":
    main()
