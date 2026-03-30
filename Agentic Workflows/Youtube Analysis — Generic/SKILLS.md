# SKILLS.md — YouTube Trend Analysis Reference

This document captures everything learned during the initial build so future Claude sessions and team members can onboard without rediscovering solved problems. Read this before starting any run.

---

## What's Already Set Up

| Thing | Status | Notes |
|-------|--------|-------|
| YouTube Data API v3 | ✅ Working | Key in `.env`. 10,000 units/day quota. |
| youtube-transcript-api | ✅ Working | Free, no quota. See API change below. |
| Anthropic Claude API | ⚠️ Needs credits | Key goes in `.env`. Add credits at console.anthropic.com. |
| Gamma MCP | ✅ Connected | Max 10 slides per generation. Cannot edit after. |
| Gmail SMTP | ⚠️ Needs App Password | Use App Password, not OAuth. See setup below. |

---

## Known Issues & Fixes

### 1. youtube-transcript-api — API changed in v0.6.x
**Problem:** `YouTubeTranscriptApi.get_transcript()` no longer exists.
**Fix:** Instantiate the class first, then call `.fetch()`.
```python
# WRONG (old API)
YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])

# CORRECT (new API)
api = YouTubeTranscriptApi()
result = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
text = " ".join(snippet.text for snippet in result)
```
The result is a `FetchedTranscript` object — iterate it for `FetchedTranscriptSnippet` items with `.text`, `.start`, `.duration`.

Errors to catch: `from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound`

---

### 2. Python 3.9 — No `X | Y` union type hints
**Problem:** Python 3.9 doesn't support `float | None` syntax in function signatures.
**Fix:** Remove return type annotations or use `Optional[float]` from `typing`.
```python
# WRONG on Python 3.9
def compute_rate(stats: dict) -> float | None:

# CORRECT
def compute_rate(stats: dict):
```

---

### 3. Gmail OAuth — Do not use
**Problem:** Google's OAuth flow has two blockers:
- `localhost refused to connect` — the local callback server doesn't work reliably in this environment
- `access_denied (Error 403)` — the OAuth app must be in "Testing" mode with the user added as an approved tester
- OOB (out-of-band) redirect URI `urn:ietf:wg:oauth:2.0:oob` was deprecated by Google in 2023

**Fix:** Use Gmail SMTP with an App Password instead. No OAuth needed.
```python
import smtplib
with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.ehlo()
    server.starttls()
    server.login(gmail_address, app_password)
    server.sendmail(from_addr, to_addr, msg.as_string())
```

**App Password setup:**
1. The Gmail account must have 2-Step Verification enabled
2. Go to myaccount.google.com/apppasswords
3. Create a new app password (name it anything, e.g. "YouTube Report")
4. Copy the 16-character password — it only shows once
5. Add to `.env` as `GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx`
6. Add the sending Gmail address to `.env` as `REPORT_EMAIL=you@gmail.com`

**Important:** App Passwords are NOT your regular Gmail password. They're a separate, limited-access key that can be revoked without affecting your main account.

---

### 4. PDF Output — pandoc + weasyprint

**When to use:** User chose PDF at intake (saves Gamma credits).

**Recommended command:**
```bash
pandoc "outputs/[slug]/report_brief.md" \
  -o "outputs/[slug]/report.pdf" \
  --pdf-engine=weasyprint \
  -V margin-top=20mm -V margin-bottom=20mm \
  -V margin-left=20mm -V margin-right=20mm
```

**Install (first time only):**
```bash
brew install pandoc
brew install weasyprint
```

**Why weasyprint over LaTeX:** No heavyweight LaTeX distribution required. Handles markdown tables and headers cleanly.

**Email with PDF attachment:** The `--attachment` flag needs to be supported in `send_email.py`. If it isn't yet, add it:
```python
from email import encoders
from email.mime.base import MIMEBase
import os

if args.attachment and os.path.exists(args.attachment):
    with open(args.attachment, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(args.attachment)}")
    msg.attach(part)
```

---

### 5. Gamma MCP — 10 slide maximum (Path A only)
**Problem:** Attempting to generate more than 10 slides throws a 400 error:
`numCards must not be greater than 10`
**Fix:** Always set `numCards: 10` or omit it.

---

### 6. Anthropic API — No credits
**Problem:** If `ANTHROPIC_API_KEY` is set but the account has no billing credits, the API returns a 400 error: `"Your credit balance is too low"`.
**Fix options:**
1. Add credits at console.anthropic.com → Plans & Billing
2. **Alternatively:** Claude (in this conversation) can perform the analysis directly by reading the data files and writing `report_brief.md` manually. The `analyze_trends.py` script is for automated/unattended runs.

---

### 7. dotenv — Must use explicit path from subdirectories
**Problem:** `load_dotenv()` without arguments doesn't find `.env` when the script runs from a subdirectory like `tools/`.
**Fix:** Always pass an explicit path:
```python
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
```

---

## YouTube Data API Quota Reference

| Operation | Units per call |
|-----------|---------------|
| `search.list` | 100 |
| `videos.list` (batch of 50) | 1 |
| `channels.list` (batch of 50) | 1 |

**Daily budget:** 10,000 units

**Typical run cost:** 15 queries × 100 = 1,500 + ~2 (video/channel details) = ~1,502 units

**If quota is exceeded:** HTTP 403 with `quotaExceeded` reason. Wait 24 hours (quota resets at midnight Pacific). Or reduce `--max-per-query`.

---

## Gamma MCP Reference (Path A — Slide Deck only)

**Tool:** `mcp__claude_ai_Gamma__generate`

Key parameters:
- `inputText` — the full slide content (use `textMode: "preserve"` when content is already written)
- `numCards` — max 10
- `textMode` — `"preserve"` (use as-is) | `"generate"` (expand brief) | `"condense"` (summarize long doc)
- `imageOptions.stylePreset` — `"abstract"` works well for business/data reports
- `cardOptions.dimensions` — `"16x9"` for standard widescreen

**Check status:** `mcp__claude_ai_Gamma__get_generation_status` — poll until `status: "completed"`, then use `gammaUrl`.

**Limitations:**
- Cannot edit a generated Gamma via MCP — user must edit in the Gamma editor
- Generation typically takes 30-90 seconds
- Each generation costs Gamma credits (34 credits for a 10-slide deck at time of writing)

---

## Running the Analysis Without Anthropic API Credits

If the Claude API has no credits, perform the analysis directly in the conversation:

1. Read the raw data: `python3 -c "import json; data=json.load(open('.tmp/youtube_raw.json')); [print(...) for v in data['videos'][:40]]"`
2. Run the stats queries to get engagement leaders, channel summaries, tag frequencies, duration breakdown
3. Write the `report_brief.md` directly using the 9-section format defined in `workflows/youtube_trend_report.md`
4. Continue to Step 4 (Gamma) as normal

This was done during the initial build on 2026-03-30 and works well.

---

## Project File Map

```
Youtube Analysis — Generic/
  CLAUDE.md           Agent instructions + intake flow
  SKILLS.md           This file — technical reference
  .env                API keys (gitignored)
  requirements.txt    Python dependencies
  tools/
    fetch_youtube_data.py    YouTube API search + stats
    fetch_transcripts.py     Caption scraping (no quota)
    analyze_trends.py        Claude API analysis
    send_email.py            Gmail SMTP delivery
  workflows/
    youtube_trend_report.md  Full SOP with commands
  outputs/
    [topic-slug]-[YYYY-MM]/  One folder per run
      queries.txt
      youtube_raw.json
      transcripts.json
      analysis.json
      report_brief.md
```

---

## First-Time Setup Checklist

- [ ] `pip3 install -r requirements.txt`
- [ ] Add `YOUTUBE_API_KEY` to `.env`
- [ ] Add `ANTHROPIC_API_KEY` to `.env` (with billing credits)
- [ ] Add `REPORT_EMAIL` to `.env` (the Gmail address you send from)
- [ ] Add `GMAIL_APP_PASSWORD` to `.env` (from myaccount.google.com/apppasswords)
