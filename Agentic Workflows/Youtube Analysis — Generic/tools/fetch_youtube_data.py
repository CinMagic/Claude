"""
fetch_youtube_data.py

Searches YouTube using queries from a queries.txt file, then fetches full
stats for each unique video and its channel.

Input:  --queries-file  path to queries.txt (one query per line)
        --output-dir    path to this run's output folder
        --max-per-query number of videos per search query (default 10)
        --days-back     only include videos published within N days (default 180)

Output: [output-dir]/youtube_raw.json

YouTube Data API v3 quota cost:
  search.list  = 100 units per call
  videos.list  = 1 unit per call (batched 50)
  channels.list = 1 unit per call (batched 50)
  15 queries × 10 results = ~1,520 units (budget: 10,000/day)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.getenv("YOUTUBE_API_KEY")


def build_youtube_client():
    if not API_KEY:
        print("ERROR: YOUTUBE_API_KEY not set in .env")
        sys.exit(1)
    return build("youtube", "v3", developerKey=API_KEY)


def load_queries(queries_file: Path) -> list[str]:
    if not queries_file.exists():
        print(f"ERROR: queries file not found: {queries_file}")
        sys.exit(1)
    queries = [line.strip() for line in queries_file.read_text().splitlines() if line.strip() and not line.startswith("#")]
    if not queries:
        print("ERROR: queries file is empty")
        sys.exit(1)
    return queries


def search_videos(youtube, query: str, max_results: int, published_after: str) -> list:
    try:
        response = youtube.search().list(
            q=query,
            part="id",
            type="video",
            maxResults=max_results,
            order="relevance",
            publishedAfter=published_after,
            relevanceLanguage="en",
        ).execute()
        return [item["id"]["videoId"] for item in response.get("items", [])]
    except HttpError as e:
        print(f"  WARNING: search failed for '{query}': {e}")
        return []


def fetch_video_details(youtube, video_ids: list) -> list:
    results = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        try:
            response = youtube.videos().list(
                id=",".join(batch),
                part="snippet,statistics,contentDetails",
            ).execute()
            results.extend(response.get("items", []))
        except HttpError as e:
            print(f"  WARNING: videos.list failed: {e}")
    return results


def fetch_channel_details(youtube, channel_ids: list) -> dict:
    results = {}
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i + 50]
        try:
            response = youtube.channels().list(
                id=",".join(batch),
                part="snippet,statistics",
            ).execute()
            for item in response.get("items", []):
                results[item["id"]] = item
        except HttpError as e:
            print(f"  WARNING: channels.list failed: {e}")
    return results


def parse_duration(iso_duration: str) -> int:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return 0
    return int(match.group(1) or 0) * 3600 + int(match.group(2) or 0) * 60 + int(match.group(3) or 0)


def compute_engagement_rate(stats: dict):
    try:
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        if views == 0:
            return None
        return round((likes + comments) / views * 100, 4)
    except (ValueError, TypeError):
        return None


def normalize_video(item: dict, channel_map: dict) -> dict:
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    content = item.get("contentDetails", {})
    channel_id = snippet.get("channelId", "")
    channel_data = channel_map.get(channel_id, {})
    channel_stats = channel_data.get("statistics", {})
    return {
        "video_id": item["id"],
        "title": snippet.get("title", ""),
        "description": snippet.get("description", "")[:500],
        "published_at": snippet.get("publishedAt", ""),
        "channel_id": channel_id,
        "channel_name": snippet.get("channelTitle", ""),
        "channel_subscriber_count": int(channel_stats.get("subscriberCount", 0)),
        "channel_video_count": int(channel_stats.get("videoCount", 0)),
        "channel_total_views": int(channel_stats.get("viewCount", 0)),
        "tags": snippet.get("tags", [])[:20],
        "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
        "duration_seconds": parse_duration(content.get("duration", "")),
        "view_count": int(stats.get("viewCount", 0)),
        "like_count": int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
        "engagement_rate": compute_engagement_rate(stats),
        "url": f"https://www.youtube.com/watch?v={item['id']}",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries-file", required=True, help="Path to queries.txt")
    parser.add_argument("--output-dir", required=True, help="Path to this run's output folder")
    parser.add_argument("--max-per-query", type=int, default=10)
    parser.add_argument("--days-back", type=int, default=180)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "youtube_raw.json"

    queries = load_queries(Path(args.queries_file))
    youtube = build_youtube_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days_back)).isoformat()

    print(f"Queries: {len(queries)} | Max per query: {args.max_per_query} | Since: {cutoff[:10]}\n")

    all_video_ids: set = set()
    query_to_ids: dict = {}

    for query in queries:
        print(f"  Searching: {query}")
        ids = search_videos(youtube, query, args.max_per_query, cutoff)
        query_to_ids[query] = ids
        all_video_ids.update(ids)
        print(f"    {len(ids)} results (unique total: {len(all_video_ids)})")

    print(f"\nFetching details for {len(all_video_ids)} unique videos...")
    video_items = fetch_video_details(youtube, list(all_video_ids))

    unique_channel_ids = list({v["snippet"]["channelId"] for v in video_items})
    print(f"Fetching channel details for {len(unique_channel_ids)} channels...")
    channel_map = fetch_channel_details(youtube, unique_channel_ids)

    videos = [normalize_video(v, channel_map) for v in video_items]
    for v in videos:
        v["matched_queries"] = query_to_ids.get(v["video_id"], [])
    videos.sort(key=lambda v: v["view_count"], reverse=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "search_params": {
            "days_back": args.days_back,
            "max_per_query": args.max_per_query,
            "queries": queries,
        },
        "total_videos": len(videos),
        "total_channels": len(channel_map),
        "videos": videos,
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(videos)} videos to {output_file}")
    print("\nTop 5 by views:")
    for v in videos[:5]:
        print(f"  [{v['view_count']:,}] {v['title'][:70]}")


if __name__ == "__main__":
    main()
