#!/usr/bin/env python3
"""Check which curated storm-chaser YouTube channels are LIVE right now and
write live.json. Run by a scheduled GitHub Action every few minutes.

Why not scrape youtube.com/<channel>/live? YouTube bot-gates datacenter IPs
(GitHub runners) with "Sign in to confirm you're not a bot" on live playback,
so the scrape reads every live channel as offline. Instead we use the official
YouTube Data API, which authenticates by key and is NOT IP-gated:

  1. Per channel, read the (free, ungated) RSS feed for its newest video ids.
     A currently-live stream is reliably the newest entry (validated: 8/8 live
     channels had the live video at RSS position 1).
  2. One batched videos.list call (part=snippet) flags which of those ids have
     snippet.liveBroadcastContent == "live".

Quota: RSS is free; videos.list is 1 unit per <=50 ids, so a sweep costs only a
few units — far under the 10k/day default even polling every 5 minutes.

Requires a YouTube Data API v3 key in the YT_API_KEY environment variable
(set as the GitHub Actions secret of the same name).
"""
import datetime
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# Curated chaser YouTube channel ids — keep in sync with kChasers in the app.
CHANNELS = {
    "UCx5ex9rJumpj-oKgVJrP4hA": "Corey Gerken",
    "UCV6hWxB0-u_IX7e-h4fEBAw": "Reed Timmer",
    "UCvBVK2ymNzPLRJrgip2GeQQ": "Max Velocity",
    "UCJHAT3Uvv-g3I8H3GhHWV7w": "Ryan Hall, Y'all",
    "UCD3KREyo3IqCLBC-4khGgIw": "WXChasing",
    "UCNPvoDpoOWevcdTHr8GyTyA": "Texas Storm Chasers",
    "UCuDoeT6EEdOTtuZh0s_gcpQ": "DL Scales",
    "UCPqLI_AohMn1jnFg8ocMyHA": "Brandon Copic",
    "UCPtizAsfQaJktz0tw9YuKLQ": "Kannon Kalton",
    "UCb0U1g5r4kH_NDMGiGRhysA": "Connor Croff",
    "UC6lUxl1KxmI7TWnAA6go1EQ": "Jaden Pappenheim",
    "UCCzfjxXs0o9h1cOgnnmc2Zw": "Tornado Paigeyy",
    "UCWMRFAo3Cvd7W8yQpQwsOQA": "John McKinney",
    "UCHt22CPAxP3_YDkB6iqDf5A": "Ben Holcomb",
    "UCRYYy0UrfyGmMKQDU1N1R3g": "Convective Chronicles",
    "UCZSDkxJS7PRw9V0_Sm6U7jg": "Freddy McKinney",
}

API_KEY = os.environ.get("YT_API_KEY", "").strip()

# Newest few RSS entries to consider per channel. A live stream is normally the
# #1 entry; a small margin guards against a fresh upload sitting above it.
_RSS_TOP_N = 4

_CTX = ssl.create_default_context()
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
_RSS_VIDEO_RE = re.compile(r"<yt:videoId>([\w-]{11})</yt:videoId>")


def _get(url):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20, context=_CTX) as r:
        return r.read().decode("utf-8", "ignore")


def _recent_video_ids(channel_id):
    """Newest few video ids from the channel's (free, ungated) RSS feed."""
    try:
        xml = _get(
            "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id
        )
        return _RSS_VIDEO_RE.findall(xml)[:_RSS_TOP_N]
    except Exception:
        return []


def _live_video_ids(video_ids):
    """Subset of video_ids whose liveBroadcastContent == 'live'. One quota unit
    per call (<=50 ids each)."""
    live = set()
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        url = (
            "https://www.googleapis.com/youtube/v3/videos?part=snippet&id="
            + ",".join(chunk)
            + "&key="
            + urllib.parse.quote(API_KEY)
        )
        data = json.loads(_get(url))
        for item in data.get("items", []):
            if item.get("snippet", {}).get("liveBroadcastContent") == "live":
                live.add(item["id"])
    return live


def main():
    if not API_KEY:
        print("ERROR: YT_API_KEY is not set (add it as a GitHub Actions secret)",
              file=sys.stderr)
        sys.exit(1)

    ids = list(CHANNELS)
    # 1. Gather candidate (recent) video ids per channel, in parallel.
    with ThreadPoolExecutor(max_workers=8) as ex:
        recents = list(ex.map(_recent_video_ids, ids))
    candidates = {}  # video_id -> channel_id (RSS is authoritative per channel)
    for cid, vids in zip(ids, recents):
        for vid in vids:
            candidates.setdefault(vid, cid)

    # 2. One batched API check of which candidates are live now.
    try:
        live_vids = _live_video_ids(list(candidates)) if candidates else set()
    except Exception as e:
        # Don't overwrite a good live.json with an empty one on an API hiccup.
        print(f"ERROR: videos.list failed: {e}", file=sys.stderr)
        sys.exit(1)
    live = sorted({candidates[v] for v in live_vids})

    out = {
        "updated": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "live": live,
    }
    with open("live.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(
        f"checked {len(ids)} channels, {len(candidates)} candidate videos, "
        f"{len(live)} live: {[CHANNELS[c] for c in live]}"
    )


if __name__ == "__main__":
    main()
