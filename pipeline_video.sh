#!/usr/bin/env bash
# pipeline_video.sh — Automated Short-Form Video Pipeline
# Usage: ./pipeline_video.sh [--topic "headline"] [--newsletter file.md]
#
# Prerequisites:
#   1. MoneyPrinterTurbo running: cd MoneyPrinterTurbo && uv run python main.py
#   2. YouTube OAuth credentials at ~/.hermes/youtube_client_secret.json
#   3. Python 3.10+ with dependencies installed
#
# Environment variables:
#   MPT_API_URL          MoneyPrinterTurbo API (default: http://127.0.0.1:8080)
#   OUTPUT_DIR           Output directory (default: ./pipeline_output)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-./pipeline_output}"
MPT_API="${MPT_API_URL:-http://127.0.0.1:8080}"

# ─── Parse arguments ──────────────────────────────────────────────────
TOPIC=""
NEWSLETTER=""
SCRIPT_FILE=""
SKIP_DISTRIBUTE=""
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --topic|-t) TOPIC="$2"; shift 2 ;;
        --newsletter|-n) NEWSLETTER="$2"; shift 2 ;;
        --script|-s) SCRIPT_FILE="$2"; shift 2 ;;
        --skip-distribute) SKIP_DISTRIBUTE="--skip-distribute"; shift ;;
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        --output-dir|-o) OUTPUT_DIR="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [--topic headline] [--newsletter file.md] [--script file.json]"
            echo "       $0 --skip-distribute --dry-run"
            exit 0
            ;;
        *) echo "Unknown flag: $1"; exit 1 ;;
    esac
done

if [[ -z "$TOPIC" && -z "$NEWSLETTER" && -z "$SCRIPT_FILE" ]]; then
    echo "ERROR: Must provide --topic, --newsletter, or --script"
    echo "Usage: $0 --topic 'Your headline here'"
    exit 1
fi

# ─── Build python command ─────────────────────────────────────────────
CMD=(
    python3 "$SCRIPT_DIR/pipeline_video.py"
    --output-dir "$OUTPUT_DIR"
    --mpt-api "$MPT_API"
)

if [[ -n "$TOPIC" ]]; then
    CMD+=(--topic "$TOPIC")
elif [[ -n "$NEWSLETTER" ]]; then
    CMD+=(--newsletter "$NEWSLETTER")
elif [[ -n "$SCRIPT_FILE" ]]; then
    CMD+=(--script "$SCRIPT_FILE")
fi

[[ -n "$SKIP_DISTRIBUTE" ]] && CMD+=("$SKIP_DISTRIBUTE")
[[ -n "$DRY_RUN" ]] && CMD+=("$DRY_RUN")

# ─── Run ──────────────────────────────────────────────────────────────
echo "🚀 Starting video pipeline..."
echo "   Output: $OUTPUT_DIR"
echo "   MPT API: $MPT_API"
echo ""

"${CMD[@]}"
