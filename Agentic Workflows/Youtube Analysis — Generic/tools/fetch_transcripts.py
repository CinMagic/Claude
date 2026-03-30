"""
fetch_transcripts.py

Fetches transcripts for the top N videos from youtube_raw.json.
Uses youtube-transcript-api (no API quota consumed).

Input:  --output-dir  path to this run's output folder (reads youtube_raw.json)
        --top-n       number of top videos to fetch transcripts for (default 25)

Output: [output-dir]/transcripts.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

_api = YouTubeTranscriptApi()


def fetch_transcript(video_id: str):
    """Returns transcript text or None if unavailable."""
    try:
        result = _api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        return " ".join(snippet.text for snippet in result)
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception as e:
        print(f"  WARNING: {video_id}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    input_file = output_dir / "youtube_raw.json"
    output_file = output_dir / "transcripts.json"

    if not input_file.exists():
        print(f"ERROR: {input_file} not found. Run fetch_youtube_data.py first.")
        sys.exit(1)

    with open(input_file) as f:
        raw_data = json.load(f)

    videos = raw_data["videos"][:args.top_n]
    print(f"Fetching transcripts for top {len(videos)} videos...\n")

    results = []
    success_count = 0
    fail_count = 0

    for i, video in enumerate(videos, 1):
        print(f"  [{i}/{len(videos)}] {video['title'][:70]}")
        transcript_text = fetch_transcript(video["video_id"])

        if transcript_text:
            word_count = len(transcript_text.split())
            print(f"    OK — {word_count:,} words")
            results.append({
                "video_id": video["video_id"],
                "title": video["title"],
                "url": video["url"],
                "view_count": video["view_count"],
                "engagement_rate": video["engagement_rate"],
                "channel_name": video["channel_name"],
                "published_at": video["published_at"],
                "word_count": word_count,
                "transcript": transcript_text,
            })
            success_count += 1
        else:
            print("    SKIP — no transcript available")
            fail_count += 1

        if i < len(videos):
            time.sleep(0.5)

    output = {
        "generated_at": raw_data["generated_at"],
        "total_fetched": success_count,
        "total_skipped": fail_count,
        "transcripts": results,
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {success_count} transcripts to {output_file}")
    print(f"Skipped {fail_count} (no captions)")


if __name__ == "__main__":
    main()
