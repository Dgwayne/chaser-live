# chaser-live

Live-status feed for the Spotter Tools Pro **Live Chasers** panel.

A scheduled GitHub Action ([.github/workflows/check.yml](.github/workflows/check.yml))
runs [`check_live.py`](check_live.py) every few minutes. It checks which curated
storm-chaser YouTube channels are **currently live** and writes [`live.json`](live.json):

```json
{ "updated": "2026-06-17T12:00:00Z", "live": ["UC...", "UC..."] }
```

The app fetches `live.json` and shows a LIVE dot, sorts live chasers first, and
dims the offline ones. Only channel ids (already-public info) live here — no
secrets in the repo. To add/remove a chaser, edit `CHANNELS` in `check_live.py`
(and the app's `kChasers`).

## How detection works

Scraping `youtube.com/<channel>/live` does **not** work from a GitHub runner:
YouTube bot-gates datacenter IPs with "Sign in to confirm you're not a bot" on
live playback, so every live channel reads as offline. Instead we use the
official **YouTube Data API** (key-authenticated, not IP-gated):

1. Read each channel's free, ungated **RSS feed** for its newest video ids — a
   live stream is reliably the newest entry.
2. One batched `videos.list` (`part=snippet`) call flags which ids have
   `liveBroadcastContent == "live"`.

Quota is tiny (a few units per sweep, vs. the 10k/day default), so 5-minute
polling is comfortable.

## Setup: the `YT_API_KEY` secret

The Action needs a free YouTube Data API v3 key:

1. https://console.cloud.google.com → create/pick a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → Credentials → Create credentials → API key**, copy it.
   (Optional: restrict it to the YouTube Data API.)
4. In this repo: **Settings → Secrets and variables → Actions → New repository
   secret**, name **`YT_API_KEY`**, paste the key.

Then **Actions → check-live → Run workflow** to verify (or wait for the next
5-minute run). Without the secret the script exits without overwriting
`live.json`.
