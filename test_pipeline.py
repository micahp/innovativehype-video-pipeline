#!/usr/bin/env python3
"""
Test the video pipeline stages with mock data.
Validates each stage independently without external API calls.

Usage:
    python test_pipeline.py
"""

import json
import os
import sys
import tempfile

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage1_script_generator import (
    generate_script_from_story,
    generate_script_from_newsletter,
    generate_script_from_json,
    extract_keywords,
    estimate_duration,
    trim_to_duration,
)
from stage2_video_renderer import build_video_request


def test_script_generation():
    """Test Stage 1: Script generation from various inputs."""
    print("=" * 60)
    print("TEST: Stage 1 — Script Generation")
    print("=" * 60)

    # Test 1: From single story
    script = generate_script_from_story(
        title="OpenAI unveils GPT-5 with autonomous agent capabilities",
        summary="The new model can browse the web, write code, and execute multi-step tasks without human intervention. Early benchmarks show a 40% improvement over GPT-4.",
    )
    assert "video_subject" in script
    assert "video_script" in script
    assert "video_terms" in script
    assert len(script["video_terms"]) > 0
    assert script["metadata"]["estimated_duration_seconds"] <= 60
    print(f"  ✅ Story→Script: {script['video_subject']}")
    print(f"     Duration: ~{script['metadata']['estimated_duration_seconds']}s")
    print(f"     Keywords: {script['video_terms']}")

    # Test 2: From newsletter markdown
    newsletter = """## GPT-5 Arrives: What It Means

OpenAI has officially released GPT-5, their most capable model yet. The system demonstrates autonomous agent behavior — it can browse the web, write and execute code, and complete multi-step tasks with minimal human guidance.

Early benchmarks paint a striking picture: 40% improvement on reasoning tasks, near-perfect scores on coding benchmarks, and the ability to maintain context over 1M+ token conversations.

This isn't incremental. This is a step change.

## Meanwhile at Google...

DeepMind quietly updated Gemini with similar capabilities. The AI race shows no signs of slowing down.
"""
    script2 = generate_script_from_newsletter(newsletter)
    assert "video_script" in script2
    assert len(script2["video_script"]) > 50
    print(f"  ✅ Newsletter→Script: {script2['video_subject']}")
    print(f"     Words: {script2['metadata']['word_count']}")

    # Test 3: From JSON
    json_input = {
        "stories": [
            {
                "title": "Meta releases open-source Llama 4",
                "summary": "Meta's latest open-source model matches GPT-4 performance at a fraction of the cost. Available on HuggingFace today.",
            }
        ]
    }
    script3 = generate_script_from_json(json_input)
    assert "video_script" in script3
    print(f"  ✅ JSON→Script: {script3['video_subject']}")

    # Test 4: Keyword extraction
    text = "OpenAI and Google are racing to build AGI with new GPU clusters from NVIDIA."
    keywords = extract_keywords(text)
    assert len(keywords) > 0
    print(f"  ✅ Keywords: {keywords}")

    # Test 5: Duration trimming
    long_text = "word " * 200
    trimmed = trim_to_duration(long_text, 55)
    assert len(trimmed.split()) < 200
    print(f"  ✅ Trim: {len(long_text.split())} → {len(trimmed.split())} words")

    # Test 6: Duration estimation
    dur = estimate_duration("This is a test sentence with exactly ten words for testing purposes.")
    print(f"  ✅ Duration estimate: {dur:.1f}s")
    assert 3 < dur < 8

    return script


def test_video_request_building():
    """Test Stage 2: Request body construction."""
    print("\n" + "=" * 60)
    print("TEST: Stage 2 — Video Request Building")
    print("=" * 60)

    script = {
        "video_subject": "GPT-5 Released",
        "video_script": "AI just took another leap. GPT-5 can now browse the web and write code autonomously.",
        "video_terms": ["ai", "technology", "robot"],
        "metadata": {"estimated_duration_seconds": 20},
    }

    body = build_video_request(script)
    assert body["video_aspect"] == "9:16"  # portrait for Shorts
    assert body["video_subject"] == "GPT-5 Released"
    assert body["subtitle_enabled"] is True
    assert len(body["video_terms"]) == 3
    print(f"  ✅ Request built: {json.dumps({k: body[k] for k in ['video_subject', 'video_aspect', 'voice_name']}, indent=2)}")


def test_end_to_end():
    """Test full pipeline with a real topic (script generation only; no API calls)."""
    print("\n" + "=" * 60)
    print("TEST: End-to-End Script Pipeline")
    print("=" * 60)

    topic = "NVIDIA unveils Blackwell Ultra GPU with 2x AI training performance"

    # Stage 1: Script
    script = generate_script_from_story(
        title=topic,
        summary="NVIDIA's new Blackwell Ultra GPU delivers double the AI training throughput of its predecessor. Major cloud providers have already placed orders worth billions.",
    )

    # Stage 2: Build request
    body = build_video_request(script)

    # Validate the full chain
    assert len(script["video_script"]) > 50, "Script too short"
    assert script["metadata"]["estimated_duration_seconds"] <= 60, "Script too long"
    assert body["video_aspect"] == "9:16", "Wrong aspect ratio"
    assert len(body["video_terms"]) >= 2, "Not enough keywords"

    print(f"  ✅ Full pipeline validated (script-only, no API)")
    print(f"     Topic: {topic}")
    print(f"     Script length: {script['metadata']['word_count']} words")
    print(f"     Est. duration: {script['metadata']['estimated_duration_seconds']}s")
    print(f"     Request keys: {list(body.keys())}")

    return script


def main():
    print("🧪 Video Pipeline Test Suite\n")

    try:
        script = test_script_generation()
        test_video_request_building()
        test_end_to_end()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)

        # Generate a sample script for reference
        sample_path = os.path.join(os.path.dirname(__file__), "sample_script.json")
        with open(sample_path, "w") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)
        print(f"\n📄 Sample script saved: {sample_path}")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
