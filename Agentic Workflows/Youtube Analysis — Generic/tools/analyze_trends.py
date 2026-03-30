"""
analyze_trends.py

Sends YouTube data and transcripts to Claude for trend analysis.
The analysis prompt adapts based on topic, goal, and target audience.

Input:  --output-dir   path to this run's output folder
        --topic        human-readable topic name (e.g. "AI for Business")
        --goal         what we're trying to learn (e.g. "content ideation and trend spotting")
        --audience     who will read this report (e.g. "content team")

Output: [output-dir]/analysis.json
        [output-dir]/report_brief.md
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-opus-4-6"


def load_data(output_dir: Path):
    raw_file = output_dir / "youtube_raw.json"
    transcript_file = output_dir / "transcripts.json"

    if not raw_file.exists():
        print(f"ERROR: {raw_file} not found. Run fetch_youtube_data.py first.")
        sys.exit(1)

    with open(raw_file) as f:
        raw = json.load(f)

    transcripts = {}
    if transcript_file.exists():
        with open(transcript_file) as f:
            t = json.load(f)
            for item in t["transcripts"]:
                transcripts[item["video_id"]] = item

    return raw, transcripts


def build_data_summary(raw: dict, transcripts: dict) -> str:
    videos = raw["videos"]
    top_videos = videos[:30]

    engagement_leaders = sorted(
        [v for v in videos if v.get("engagement_rate") and v["view_count"] >= 1000],
        key=lambda v: v["engagement_rate"],
        reverse=True,
    )[:15]

    from collections import defaultdict
    channel_appearances = defaultdict(lambda: {"name": "", "subscribers": 0, "videos_in_results": 0, "total_views_in_results": 0})
    for v in videos:
        c = channel_appearances[v["channel_id"]]
        c["name"] = v["channel_name"]
        c["subscribers"] = v["channel_subscriber_count"]
        c["videos_in_results"] += 1
        c["total_views_in_results"] += v["view_count"]

    top_channels = sorted(channel_appearances.values(), key=lambda c: c["total_views_in_results"], reverse=True)[:10]

    durations = [v["duration_seconds"] for v in videos if v["duration_seconds"] > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0

    tag_freq: dict = {}
    for v in videos:
        for tag in v.get("tags", []):
            tag_lower = tag.lower()
            tag_freq[tag_lower] = tag_freq.get(tag_lower, 0) + 1
    top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:30]

    transcript_samples = []
    for v in top_videos:
        if v["video_id"] in transcripts:
            t = transcripts[v["video_id"]]
            snippet = t["transcript"][:800].replace("\n", " ")
            transcript_samples.append(
                f"VIDEO: {v['title']}\nVIEWS: {v['view_count']:,} | ENGAGEMENT: {v.get('engagement_rate', 'N/A')}%\n{snippet}...\n"
            )
        if len(transcript_samples) >= 5:
            break

    lines = [
        f"DATASET: {len(videos)} YouTube videos",
        f"Date range: last {raw['search_params']['days_back']} days",
        f"Total unique channels: {raw['total_channels']}",
        f"Average video duration: {avg_duration/60:.1f} minutes",
        "",
        "=== TOP 30 VIDEOS BY VIEWS ===",
    ]
    for v in top_videos:
        lines.append(
            f"- [{v['view_count']:,} views | {v.get('engagement_rate', 'N/A')}% eng | "
            f"{v['duration_seconds']//60}min] {v['title']} | {v['channel_name']}"
        )
    lines += ["", "=== TOP 15 BY ENGAGEMENT RATE (min 1k views) ==="]
    for v in engagement_leaders:
        lines.append(f"- [{v['engagement_rate']}% eng | {v['view_count']:,} views] {v['title']} | {v['channel_name']}")
    lines += ["", "=== TOP CHANNELS IN RESULTS ==="]
    for c in top_channels:
        lines.append(
            f"- {c['name']}: {c['subscribers']:,} subs | {c['videos_in_results']} videos | "
            f"{c['total_views_in_results']:,} views in results"
        )
    lines += ["", "=== TOP 30 TAGS ===", ", ".join(f"{tag}({count})" for tag, count in top_tags)]
    lines += ["", "=== TRANSCRIPT SAMPLES ==="]
    lines.extend(transcript_samples)

    return "\n".join(lines)


def call_claude(data_summary: str, topic: str, goal: str, audience: str) -> str:
    client = anthropic.Anthropic(api_key=API_KEY)

    prompt = f"""You are a YouTube content strategist and market analyst. You've been given data about top-performing YouTube videos in the **{topic}** niche.

**Goal of this analysis:** {goal}
**Report audience:** {audience}

Analyze this data and produce a comprehensive trend report that will be turned into a professional slide deck. Be specific, data-driven, and actionable. Reference actual titles, channels, and numbers from the data.

Here is the raw data:

{data_summary}

---

Produce a detailed analysis covering all sections below. Each section should be grounded in the actual data.

## 1. EXECUTIVE SUMMARY
2-3 sentences capturing the single most important insight from this dataset for someone focused on {topic}.

## 2. TRENDING TOPICS & THEMES
The 5-7 dominant themes performing best. For each:
- Theme name
- Why it's resonating (data-backed)
- Example high-performing titles
- Opportunity level (High/Medium/Low)

## 3. ENGAGEMENT DEEP DIVE
- What content types get the highest engagement rates (not just views)?
- What does high engagement signal about audience intent?
- Patterns among high-engagement videos (title, length, format)

## 4. AUDIENCE PAIN POINTS
Top 5-7 pain points the audience has around {topic}, based on video titles, tags, and transcripts. These are the problems people are actively searching for answers to.

## 5. CONTENT FORMAT ANALYSIS
- What video lengths perform best?
- What title patterns work (numbers, questions, how-tos, contrast)?
- Any format or style patterns among top performers?

## 6. TOP CHANNELS TO WATCH
The 5 most influential channels in this space. What's their positioning and why does it work?

## 7. CONTENT GAPS & OPPORTUNITIES
What is the audience hungry for that isn't being well-served? Specific, actionable gaps.

## 8. RECOMMENDED CONTENT IDEAS
8-10 specific, ready-to-use video ideas. For each:
- Suggested title (optimized for search + clicks)
- Target keyword(s)
- Why it will perform

## 9. KEY METRICS SNAPSHOT
Clean summary table: total videos, view range, avg engagement, top video, top channel, optimal length, top tags.

Format as clean markdown."""

    print("Sending data to Claude for analysis...")
    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--topic", required=True, help="Human-readable topic name")
    parser.add_argument("--goal", default="content ideation, competitor research, and trend spotting")
    parser.add_argument("--audience", default="content team")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        print("Add credits at console.anthropic.com, then add the key to .env")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    brief_file = output_dir / "report_brief.md"
    analysis_file = output_dir / "analysis.json"

    print(f"Topic: {args.topic}")
    print(f"Goal: {args.goal}")
    print(f"Audience: {args.audience}\n")

    raw, transcripts = load_data(output_dir)
    print(f"Loaded {raw['total_videos']} videos, {len(transcripts)} transcripts")

    data_summary = build_data_summary(raw, transcripts)
    analysis_text = call_claude(data_summary, args.topic, args.goal, args.audience)

    with open(brief_file, "w") as f:
        f.write(f"# {args.topic} — YouTube Trend Report\n")
        f.write(f"*Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y')} | Goal: {args.goal}*\n\n")
        f.write(analysis_text)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_used": MODEL,
        "topic": args.topic,
        "goal": args.goal,
        "audience": args.audience,
        "videos_analyzed": raw["total_videos"],
        "transcripts_included": len(transcripts),
        "analysis_markdown": analysis_text,
    }
    with open(analysis_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nReport brief → {brief_file}")
    print(f"Analysis JSON → {analysis_file}")


if __name__ == "__main__":
    main()
