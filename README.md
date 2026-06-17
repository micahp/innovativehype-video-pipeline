# Automated AI Video Pipeline

Automated short-form video pipeline for the **Innovative Hype** brand:
script generation → video rendering → multi-platform distribution.

Built for Hermes Kanban task `t_db9658c0`.

## Architecture

```
AI News / Topic
    │
    ▼
┌─────────────────────────────────┐
│ Stage 1: Script Generator       │
│   stage1_script_generator.py    │
│   Input:  news headlines/topics │
│   Output: script.json           │
│   Format: hook + insight + CTA  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ Stage 2: Video Renderer         │
│   stage2_video_renderer.py      │
│   Input:  script.json           │
│   Calls:  MoneyPrinterTurbo API │
│   Output: video.mp4 (9:16)      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ Stage 3: Distributor            │
│   stage3_distributor.py         │
│   Input:  video.mp4             │
│   Posts:  YouTube Shorts        │
│   (Instagram/TikTok documented) │
└─────────────────────────────────┘
```

## Quick Start

### Prerequisites

```bash
# Python dependencies
pip install requests google-api-python-client google-auth-oauthlib google-auth-httplib2

# MoneyPrinterTurbo (video generation engine)
git clone https://github.com/harry0703/MoneyPrinterTurbo
cd MoneyPrinterTurbo
cp config.example.toml config.toml
# Edit config.toml: set pexels_api_keys and llm_provider API keys
uv run python main.py  # starts API at http://127.0.0.1:8080
```

### Run the Pipeline

```bash
# Full pipeline from a single topic
./pipeline_video.sh --topic "GPT-5 released with autonomous agent capabilities"

# From a newsletter markdown file
./pipeline_video.sh --newsletter newsletter.md --output-dir ./out

# Test mode — no API calls
./pipeline_video.sh --topic "Test headline" --dry-run

# Generate video only, skip distribution
./pipeline_video.sh --topic "NVIDIA Blackwell Ultra" --skip-distribute
```

Or use Python directly:

```bash
python3 pipeline_video.py --topic "Your headline" --output-dir ./out
```

## Stage Details

### Stage 1: Script Generator (`stage1_script_generator.py`)

Converts AI news into short-form video scripts (30-60 seconds).

**Input formats:**
- `--topic "Single headline"` — bare topic
- `--input news.json` — JSON with `{"stories": [{"title": "...", "summary": "..."}]}`
- `--newsletter newsletter.md` — Markdown with `## Headline` + body

**Script structure:**
```
[0-5s]   Hook — attention grabber (rotates through 8 patterns)
[5-45s]  Core Insight — what happened and why it matters
[45-55s] CTA — "Subscribe to Innovative Hype. Link in bio."
```

**Output** (`script.json`):
```json
{
  "video_subject": "GPT-5 released...",
  "video_script": "This changes everything.\n\nGPT-5...\n\nSubscribe...",
  "video_terms": ["ai", "technology", "code"],
  "metadata": {
    "estimated_duration_seconds": 45.2,
    "word_count": 120,
    "hook": "..."
  }
}
```

### Stage 2: Video Renderer (`stage2_video_renderer.py`)

Calls MoneyPrinterTurbo API to generate the video.

**API:** `POST /videos` with `TaskVideoRequest` body
**Format:** 9:16 vertical, AI voiceover, burned-in subtitles, stock footage from Pexels
**Voice:** `en-US-JennyNeural` (configurable via `config.mpt.json`)
**Polling:** Checks task status every 5s, timeout 10min

```bash
# Environment variables
export MPT_API_URL=http://127.0.0.1:8080
export MPT_VOICE_NAME=en-US-JennyNeural

python3 stage2_video_renderer.py --script script.json --output video.mp4
python3 stage2_video_renderer.py --script script.json --config config.mpt.json --output video.mp4
python3 stage2_video_renderer.py --script script.json --dry-run  # validate only
```

### Stage 3: Distributor (`stage3_distributor.py`)

Uploads to YouTube Shorts (primary) with Instagram and TikTok documented.

#### YouTube Shorts (✅ Ready)
- OAuth 2.0 via Google Cloud Console
- Free quota: ~6 uploads/day
- Videos under 60s, 9:16 auto-classify as Shorts

**Setup:**
1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (Desktop app)
3. Enable YouTube Data API v3
4. Download JSON → save as `~/.hermes/youtube_client_secret.json`
5. First run opens browser for OAuth consent

```bash
python3 stage3_distributor.py --video video.mp4 --platform youtube
python3 stage3_distributor.py --video video.mp4 --platform youtube --privacy unlisted
```

#### Instagram Reels (⚠️ Needs App Review)
- Requires Facebook App with `instagram_content_publish` permission
- Instagram Professional Account + Facebook Page
- Page Publishing Authorization (PPA)
- App Review takes days to weeks
- Video must be publicly accessible URL (not local file)

**Setup:** See [Instagram Content Publishing API docs](https://developers.facebook.com/docs/instagram-platform/content-publishing)

```bash
export INSTAGRAM_ACCESS_TOKEN="EAA..."
export INSTAGRAM_IG_USER_ID="178414..."
python3 stage3_distributor.py --video video.mp4 --platform instagram
```

#### TikTok (⚠️ Restricted)
- Content Posting API requires approved developer account
- Most developers cannot obtain `video.publish` permission
- See [TikTok for Developers](https://developers.tiktok.com/products/content-posting-api)

## Automation (Hermes Cron Job)

Recommended: run the pipeline daily via Hermes cron.

```bash
# Create the cron job (run from Hermes)
# This assumes MoneyPrinterTurbo is running and YouTube OAuth is configured

hermes cronjob create \
  --name "Daily AI Video Pipeline" \
  --schedule "0 8 * * *" \
  --prompt "Run the video pipeline for today's top AI story. Use pipeline_video.py with --topic set to today's headline." \
  --workdir /Users/micah/.hermes/kanban/workspaces/t_db9658c0 \
  --skills kanban-worker \
  --deliver origin
```

Or use a `cronjob` tool call from within Hermes:

```
cronjob(
  action='create',
  name='Daily AI Video Pipeline',
  schedule='0 8 * * *',
  prompt="Generate a short-form AI news video: pick the top AI story, run pipeline_video.py --topic '<headline>' --output-dir ./pipeline_output, and report the result.",
  workdir='/Users/micah/.hermes/kanban/workspaces/t_db9658c0',
  skills=['kanban-worker'],
)
```

## Files

| File | Purpose |
|------|---------|
| `stage1_script_generator.py` | News → video script (hook + insight + CTA) |
| `stage2_video_renderer.py` | Script → video via MoneyPrinterTurbo API |
| `stage3_distributor.py` | Video → YouTube Shorts (Instagram/TikTok documented) |
| `pipeline_video.py` | Orchestrator: wires all 3 stages |
| `pipeline_video.sh` | Shell wrapper for pipeline_video.py |
| `config.mpt.json` | MoneyPrinterTurbo config (voice, subtitle, style) |
| `test_pipeline.py` | Test suite: validates all stages |
| `sample_script.json` | Example generated script |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MPT_API_URL` | `http://127.0.0.1:8080` | MoneyPrinterTurbo API URL |
| `MPT_VOICE_NAME` | `en-US-JennyNeural` | TTS voice for narration |
| `MPT_VOICE_RATE` | `1.0` | Voice speed multiplier |
| `YOUTUBE_CREDENTIALS_FILE` | `~/.hermes/youtube_client_secret.json` | Google OAuth client secret |
| `YOUTUBE_TOKEN_FILE` | `~/.hermes/youtube_token.json` | Cached OAuth token |
| `INSTAGRAM_ACCESS_TOKEN` | (none) | Instagram Graph API token |
| `INSTAGRAM_IG_USER_ID` | (none) | Instagram Professional Account ID |

### MoneyPrinterTurbo Config (`config.mpt.json`)

Override video style without editing MPT's `config.toml`:

```json
{
  "video_aspect": "9:16",
  "voice_name": "en-US-JennyNeural",
  "bgm_volume": 0.15,
  "subtitle_enabled": true,
  "font_size": 54
}
```

## Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| LLM API (OpenRouter) | ~$5-10 (1 script/day) |
| TTS (Edge TTS, free) | $0 |
| Stock footage (Pexels, free) | $0 |
| YouTube API | Free (within quota) |
| **Total** | **~$5-10/month** |

## Testing

```bash
# Run the test suite (no API calls needed)
python3 test_pipeline.py

# Dry run full pipeline
python3 pipeline_video.py --topic "Test" --dry-run

# Generate a sample script
python3 stage1_script_generator.py --topic "Your headline" --output test.json
```

## Platform Status

| Platform | API Status | Automation | Notes |
|----------|-----------|------------|-------|
| YouTube Shorts | ✅ Ready | Full | OAuth, 6 uploads/day free |
| Instagram Reels | ⚠️ Pending | Needs App Review | FB App + PPA required |
| TikTok | ❌ Restricted | Manual only | API access highly restricted |

## Discovery Report

Full research and tool evaluation in the [parent task report](../t_124f75d6/report.md):
- Brand audit: Innovative Hype (dormant, conversational, AI-themed)
- 20+ RSS AI news sources evaluated
- 10+ video generation repos (MoneyPrinterTurbo selected)
- 4 distribution platforms analyzed
- Phased roadmap (P0-P5)

## License

MIT — match MoneyPrinterTurbo's license for pipeline code.
