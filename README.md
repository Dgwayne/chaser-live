# chaser-live

Live-status feed for the Spotter Tools Pro **Live Chasers** panel.

A scheduled GitHub Action ([.github/workflows/check.yml](.github/workflows/check.yml))
runs [`check_live.py`](check_live.py) every few minutes. It checks which curated
storm-chaser YouTube channels are **currently live** (by parsing each channel's
`/live` player response — `videoDetails.isLive`) and writes [`live.json`](live.json):

```json
{ "updated": "2026-06-17T12:00:00Z", "live": ["UC...", "UC..."] }
```

The app fetches `live.json` and shows a LIVE dot, sorts live chasers first, and
dims the offline ones. Only channel ids (already-public info) live here — no
secrets. To add/remove a chaser, edit `CHANNELS` in `check_live.py` (and the
app's `kChasers`).
