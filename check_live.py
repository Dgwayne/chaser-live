#!/usr/bin/env python3
"""Check which curated storm-chaser YouTube channels are LIVE right now and
write live.json. Run by a scheduled GitHub Action every few minutes.

Detection: fetch youtube.com/channel/<id>/live, parse the MAIN
ytInitialPlayerResponse, and treat the channel as live only when
videoDetails.isLive is true. (A raw "isLive":true substring false-positives on
recommended videos in the sidebar; the brace-balanced parse avoids that.)
"""
import json
import re
import ssl
import urllib.request
import datetime
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

_CTX = ssl.create_default_context()
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    # Pre-accept the cookie consent so datacenter IPs (GitHub runners) get the
    # real watch page instead of consent.youtube.com (which omits the player
    # response and made every channel read as "not live").
    "Cookie": "SOCS=CAI; CONSENT=YES+1",
}

# Diagnostics surfaced in the Action log so a datacenter-IP block is obvious.
_stats = {"fetched": 0, "player": 0, "consent": 0, "error": 0}


def _fetch(url):
    # Force US/English to avoid the EU consent interstitial.
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(url + sep + "hl=en&gl=US", headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20, context=_CTX) as r:
        return r.read().decode("utf-8", "ignore")


def _player_response(html):
    """Brace-balanced extraction of the ytInitialPlayerResponse JSON object."""
    m = re.search(r"ytInitialPlayerResponse\s*=\s*\{", html)
    if not m:
        return None
    i = m.end() - 1
    start = i
    depth = 0
    in_str = False
    esc = False
    while i < len(html):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        i += 1
    return None


def is_live(channel_id):
    try:
        html = _fetch(f"https://www.youtube.com/channel/{channel_id}/live")
        _stats["fetched"] += 1
        if "consent.youtube.com" in html or "/sorry/" in html:
            _stats["consent"] += 1
        pr = _player_response(html)
        if not pr:
            return False
        _stats["player"] += 1
        return pr.get("videoDetails", {}).get("isLive") is True
    except Exception:
        _stats["error"] += 1
        return False


def main():
    ids = list(CHANNELS)
    with ThreadPoolExecutor(max_workers=6) as ex:
        flags = list(ex.map(is_live, ids))
    live = [cid for cid, ok in zip(ids, flags) if ok]
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
        f"diagnostics: fetched={_stats['fetched']} "
        f"got-player-response={_stats['player']} consent-page={_stats['consent']} "
        f"errors={_stats['error']} (of {len(ids)} channels)"
    )
    print(f"{len(live)} live: {[CHANNELS[c] for c in live]}")


if __name__ == "__main__":
    main()
