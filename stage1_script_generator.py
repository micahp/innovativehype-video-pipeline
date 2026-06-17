#!/usr/bin/env python3
"""
Stage 1: Script Generator
Converts AI news stories into short-form video scripts (30-60 seconds).
Output format compatible with MoneyPrinterTurbo API.

Usage:
    python stage1_script_generator.py --input news.json --output script.json
    python stage1_script_generator.py --topic "OpenAI releases GPT-5" --output script.json
    python stage1_script_generator.py --newsletter newsletter.md --output script.json

Input formats supported:
    - JSON: {"stories": [{"title": "...", "summary": "..."}]}
    - Markdown newsletter text
    - Single topic string via --topic flag

Output: JSON with video_subject, video_script, video_terms, and metadata
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Optional


# ─── Brand Voice Constants ────────────────────────────────────────────────

BRAND = "Innovative Hype"
AUTHOR = "Micah 'Geo' Peoples"
CTA_TEXT = "Subscribe to Innovative Hype for more AI insights. Link in bio."
HOOK_PATTERNS = [
    "This changes everything.",
    "You need to see this.",
    "AI just took another leap.",
    "Here's what everyone's missing.",
    "The biggest AI story nobody's talking about.",
    "This slipped under the radar.",
    "Silicon Valley is buzzing about this.",
    "The numbers don't lie.",
]


def estimate_duration(text: str, wpm: int = 155) -> float:
    """Estimate voiceover duration in seconds based on word count."""
    words = len(text.split())
    return (words / wpm) * 60


def trim_to_duration(text: str, max_seconds: int = 55) -> str:
    """Trim text to fit within max_seconds at ~155 wpm."""
    words = text.split()
    max_words = int((max_seconds / 60) * 155)
    if len(words) <= max_words:
        return text
    # Cut at sentence boundary near max_words
    trimmed = " ".join(words[:max_words])
    last_period = trimmed.rfind(".")
    if last_period > max_words * 0.6:
        return trimmed[: last_period + 1]
    return trimmed


def extract_keywords(text: str, max_keywords: int = 5) -> list[str]:
    """Extract visual search keywords from text for stock footage."""
    # Simple keyword extraction — pull capitalized phrases, company names, tech terms
    keywords = set()

    # Named entities: capitalized multi-word phrases
    caps = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
    keywords.update(t.strip().lower() for t in caps[:3])

    # Tech terms
    tech_terms = [
        "ai", "artificial intelligence", "machine learning", "neural network",
        "data center", "robot", "automation", "chip", "gpu", "cloud",
        "startup", "silicon valley", "code", "algorithm", "software",
        "headquarters", "office", "meeting", "presentation", "screen",
        "futuristic", "technology", "digital", "innovation",
    ]
    for term in tech_terms:
        if term.lower() in text.lower():
            keywords.add(term.lower())

    # Ensure we have enough
    if len(keywords) < 3:
        keywords.update(["technology", "ai", "digital"])

    return list(keywords)[:max_keywords]


def generate_script_from_story(
    title: str,
    summary: str,
    max_duration: int = 55,
) -> dict:
    """
    Generate a short-form video script from a single news story.

    Structure:
        [0-5s]  Hook — attention grabber
        [5-45s] Core Insight — what happened and why it matters
        [45-55s] CTA — subscribe/engage
    """
    # Pick a hook
    hook = HOOK_PATTERNS[hash(title) % len(HOOK_PATTERNS)]

    # Build the core insight (trim to fit duration budget)
    hook_duration = estimate_duration(hook)
    cta_duration = estimate_duration(CTA_TEXT)
    insight_budget = int(max_duration - hook_duration - cta_duration - 3)

    # Build insight: title + summary, conversational tone
    insight = f"{title}. {summary}"

    # Trim if needed
    insight_trimmed = trim_to_duration(insight, insight_budget)

    # Full script
    full_script = f"{hook}\n\n{insight_trimmed}\n\n{CTA_TEXT}"

    # Extract keywords for visual search
    combined_text = f"{title} {summary} {full_script}"
    keywords = extract_keywords(combined_text)

    # Calculate timing
    total_duration = estimate_duration(full_script)

    return {
        "video_subject": title[:100],  # Topic for MPT's LLM
        "video_script": full_script,    # Narration + subtitles
        "video_terms": keywords,        # Stock footage search terms
        "metadata": {
            "source_title": title,
            "hook": hook,
            "estimated_duration_seconds": round(total_duration, 1),
            "word_count": len(full_script.split()),
            "generated_at": datetime.now().isoformat(),
            "brand": BRAND,
        },
    }


def generate_script_from_newsletter(
    text: str,
    max_duration: int = 55,
) -> dict:
    """
    Extract the top story from a newsletter and generate a script.
    Falls back to treating the whole text as a single topic if no structure found.
    """
    # Try to find a headline (## Heading or first bold line)
    headlines = re.findall(r"^##?\s+(.+)$", text, re.MULTILINE)
    if headlines:
        title = headlines[0].strip()
        # Get the paragraph after the first headline
        parts = text.split(headlines[0], 1)
        if len(parts) > 1:
            body = parts[1].strip()
            # Take first 2-3 sentences
            sentences = re.split(r"(?<=[.!?])\s+", body)
            summary = " ".join(sentences[:3])
        else:
            summary = text[:500]
    else:
        # No markdown structure — use first sentence as title
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        title = sentences[0][:100] if sentences else "AI News Update"
        summary = " ".join(sentences[1:4]) if len(sentences) > 1 else text[:500]

    return generate_script_from_story(title, summary, max_duration)


def generate_script_from_json(
    data: dict,
    max_duration: int = 55,
) -> dict:
    """Generate a script from JSON input with stories array."""
    stories = data.get("stories", [])
    if not stories:
        # Try alternate keys
        stories = data.get("articles", data.get("items", data.get("news", [])))
    if not stories:
        raise ValueError("No stories found in JSON. Expected key: 'stories', 'articles', 'items', or 'news'")

    # Pick the first story
    story = stories[0]
    title = story.get("title", story.get("headline", "AI News"))
    summary = story.get("summary", story.get("description", story.get("body", "")))

    return generate_script_from_story(title, summary, max_duration)


def main():
    parser = argparse.ArgumentParser(
        description="Generate short-form video scripts from AI news",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input news_batch.json --output script.json
  %(prog)s --topic "OpenAI drops GPT-5 with agent capabilities" --output script.json
  %(prog)s --newsletter newsletter.md --output script.json --max-duration 45
        """,
    )
    parser.add_argument("--input", "-i", help="JSON file with stories array")
    parser.add_argument("--topic", "-t", help="Single topic/headline string")
    parser.add_argument("--newsletter", "-n", help="Markdown newsletter file")
    parser.add_argument("--output", "-o", default="script.json", help="Output JSON file")
    parser.add_argument("--max-duration", type=int, default=55, help="Max video duration in seconds")
    args = parser.parse_args()

    if args.topic:
        script = generate_script_from_story(args.topic, "", args.max_duration)
    elif args.newsletter:
        with open(args.newsletter) as f:
            text = f.read()
        script = generate_script_from_newsletter(text, args.max_duration)
    elif args.input:
        with open(args.input) as f:
            data = json.load(f)
        script = generate_script_from_json(data, args.max_duration)
    else:
        parser.print_help()
        sys.exit(1)

    with open(args.output, "w") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)

    print(f"✅ Script generated: {args.output}")
    print(f"   Subject: {script['video_subject']}")
    print(f"   Duration: ~{script['metadata']['estimated_duration_seconds']}s")
    print(f"   Keywords: {', '.join(script['video_terms'])}")
    print(f"   Words: {script['metadata']['word_count']}")

    return script


if __name__ == "__main__":
    main()
