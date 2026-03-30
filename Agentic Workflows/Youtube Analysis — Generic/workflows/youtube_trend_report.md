# Workflow: YouTube Trend Report (Generic)

## Objective
Analyze YouTube content for any topic or niche. Produce a professional slide deck covering trending topics, audience pain points, top channels, content gaps, and ready-to-use video ideas. Deliver via email if requested.

## Prerequisites
- `YOUTUBE_API_KEY` in `.env`
- `ANTHROPIC_API_KEY` in `.env` (with credits at console.anthropic.com)
- `REPORT_EMAIL` + `GMAIL_APP_PASSWORD` in `.env` (only needed for email delivery)
- Dependencies installed: `pip3 install -r requirements.txt`

---

## Step 0 — Intake (Claude does this, not a script)

Before running any tool, Claude asks the user:

1. **Topic / niche** — what are we analyzing?
2. **Goal** — content ideation / competitor research / trend spotting / all of the above?
3. **Report audience** — who reads this? (content team, client, personal use)
4. **Keywords or channels to include/exclude** — any specific ones?
5. **Lookback window** — 30 / 90 / 180 days (default 180)
6. **Output format** — Gamma slide deck (polished, uses Gamma credits) or PDF (free, no external service)?
7. **Email delivery** — yes/no, and which address?

After intake, Claude:
- Generates 12–15 search queries covering the topic from multiple angles
- Creates the output directory: `outputs/[topic-slug]-[YYYY-MM]/`
- Writes queries to `outputs/[topic-slug]-[YYYY-MM]/queries.txt`

**Query generation guidelines:**
- Cover the core topic (3-4 queries)
- Cover pain points and problems the audience has (3-4 queries)
- Cover outcome-based searches ("how to make money with X", "X for beginners") (2-3 queries)
- Cover trending sub-topics or adjacent angles (2-3 queries)
- Include year ("2025", "2026") in 2-3 queries to bias toward recent content

**Topic slug format:** lowercase, hyphens, no spaces. e.g. `ai-for-business`, `personal-finance`, `shopify-ecommerce`

---

## Step 1 — Fetch YouTube Data
**Tool:** `tools/fetch_youtube_data.py`

```bash
python3 tools/fetch_youtube_data.py \
  --queries-file "outputs/[topic-slug]-[YYYY-MM]/queries.txt" \
  --output-dir "outputs/[topic-slug]-[YYYY-MM]" \
  --max-per-query 10 \
  --days-back 180
```

**Output:** `outputs/[topic-slug]-[YYYY-MM]/youtube_raw.json`

**Quota cost:** ~100 units per query + 1 unit per video. 15 queries × 10 results ≈ 1,520 units/day (budget: 10,000).

**Edge cases:**
- HTTP 403 quotaExceeded → wait 24h or reduce `--max-per-query`
- Irrelevant videos will appear in results — Claude's analysis filters them naturally

---

## Step 2 — Fetch Transcripts
**Tool:** `tools/fetch_transcripts.py`

```bash
python3 tools/fetch_transcripts.py \
  --output-dir "outputs/[topic-slug]-[YYYY-MM]" \
  --top-n 25
```

**Output:** `outputs/[topic-slug]-[YYYY-MM]/transcripts.json`

**No API quota consumed.** Uses youtube-transcript-api to scrape caption files.

**Edge cases:**
- ~60-70% of videos have English captions; the rest are skipped gracefully
- Auto-generated captions are lower quality but still useful for theme extraction

---

## Step 3 — Analyze with Claude
**Tool:** `tools/analyze_trends.py`

```bash
python3 tools/analyze_trends.py \
  --output-dir "outputs/[topic-slug]-[YYYY-MM]" \
  --topic "Your Topic Name" \
  --goal "content ideation and trend spotting" \
  --audience "content team"
```

**Output:**
- `outputs/[topic-slug]-[YYYY-MM]/report_brief.md` — full markdown analysis
- `outputs/[topic-slug]-[YYYY-MM]/analysis.json` — metadata

**Edge cases:**
- If ANTHROPIC_API_KEY has no credits, script exits with a clear error and billing URL
- Uses claude-opus-4-6 for best quality; ~30-60 second response time

**NOTE:** If the Anthropic API key has no credits, Claude can perform the analysis directly
in this conversation. Read the data files and write the report_brief.md manually.
See SKILLS.md for how this was done during the initial build.

---

## Step 4 — Generate Report Output (Claude does this directly)

Choose the path based on the user's intake answer for **Output format**.

---

### Path A — Gamma Slide Deck
**Tool:** Gamma MCP (Claude calls this, not a Python script)

After Step 3, Claude:
1. Reads `outputs/[topic-slug]-[YYYY-MM]/report_brief.md`
2. Calls Gamma MCP `generate` tool with a 10-slide structured deck
3. Saves the returned Gamma URL

**Gamma call guidelines:**
- `numCards`: 10 (Gamma maximum)
- `textMode`: "preserve" (content is already fully written)
- `imageOptions.source`: "aiGenerated"
- `imageOptions.stylePreset`: "abstract" or "photorealistic" depending on topic
- `cardOptions.dimensions`: "16x9"
- Title slide should include topic name, date, and dataset size

**Known Gamma constraints (see SKILLS.md):**
- Maximum 10 slides per generation
- Cannot edit after generation — user must use Gamma editor for changes
- Generation takes 30-90 seconds; poll with `get_generation_status`

---

### Path B — PDF
**Tool:** `pandoc` (command line) — free, no external service, no credits consumed

```bash
pandoc "outputs/[topic-slug]-[YYYY-MM]/report_brief.md" \
  -o "outputs/[topic-slug]-[YYYY-MM]/report.pdf" \
  --pdf-engine=weasyprint \
  -V margin-top=20mm -V margin-bottom=20mm \
  -V margin-left=20mm -V margin-right=20mm
```

**Fallback if weasyprint not available:**
```bash
pandoc "outputs/[topic-slug]-[YYYY-MM]/report_brief.md" \
  -o "outputs/[topic-slug]-[YYYY-MM]/report.pdf"
```
(uses pandoc's default PDF engine — requires a LaTeX distribution like BasicTeX or MacTeX)

**Install options (first time only):**
```bash
brew install pandoc          # pandoc itself
brew install weasyprint      # lightweight PDF engine (recommended — no LaTeX needed)
```

**Output:** `outputs/[topic-slug]-[YYYY-MM]/report.pdf`

After generating, confirm the file exists and tell the user the path.

---

## Step 5 — Email Delivery (optional)
**Tool:** `tools/send_email.py`

**If output was a Gamma slide deck:**
```bash
python3 tools/send_email.py \
  --to "recipient@example.com" \
  --topic "Your Topic Name" \
  --deck-url "https://gamma.app/docs/..." \
  --report-brief "outputs/[topic-slug]-[YYYY-MM]/report_brief.md"
```

**If output was a PDF:**
```bash
python3 tools/send_email.py \
  --to "recipient@example.com" \
  --topic "Your Topic Name" \
  --attachment "outputs/[topic-slug]-[YYYY-MM]/report.pdf" \
  --report-brief "outputs/[topic-slug]-[YYYY-MM]/report_brief.md"
```

**Prerequisites:** `REPORT_EMAIL` and `GMAIL_APP_PASSWORD` set in `.env`.
See SKILLS.md for App Password setup instructions.

**Note:** The `--attachment` flag requires `send_email.py` to support it. See SKILLS.md for the PDF email implementation.

---

## Full Run Example

```bash
# 1. Install dependencies (first time only)
pip3 install -r requirements.txt

# 2. Fetch data (after Claude writes queries.txt)
python3 tools/fetch_youtube_data.py \
  --queries-file "outputs/personal-finance-2026-04/queries.txt" \
  --output-dir "outputs/personal-finance-2026-04"

# 3. Fetch transcripts
python3 tools/fetch_transcripts.py \
  --output-dir "outputs/personal-finance-2026-04"

# 4. Analyze
python3 tools/analyze_trends.py \
  --output-dir "outputs/personal-finance-2026-04" \
  --topic "Personal Finance for Millennials" \
  --goal "content ideation and competitor research" \
  --audience "content team"

# 5a. Generate Gamma slide deck (if user chose Gamma)
# Tell Claude: "Read outputs/personal-finance-2026-04/report_brief.md and generate the Gamma slide deck"

# 5b. Generate PDF (if user chose PDF — no Gamma credits used)
pandoc "outputs/personal-finance-2026-04/report_brief.md" \
  -o "outputs/personal-finance-2026-04/report.pdf" \
  --pdf-engine=weasyprint

# 6. Send email (optional)
# Gamma deck:
python3 tools/send_email.py \
  --to "team@example.com" \
  --topic "Personal Finance for Millennials" \
  --deck-url "PASTE_GAMMA_URL" \
  --report-brief "outputs/personal-finance-2026-04/report_brief.md"

# PDF:
python3 tools/send_email.py \
  --to "team@example.com" \
  --topic "Personal Finance for Millennials" \
  --attachment "outputs/personal-finance-2026-04/report.pdf" \
  --report-brief "outputs/personal-finance-2026-04/report_brief.md"
```

---

## Output Files Per Run

All files live in `outputs/[topic-slug]-[YYYY-MM]/`:

| File | Purpose |
|------|---------|
| `queries.txt` | Search queries (written by Claude during intake) |
| `youtube_raw.json` | Raw video + channel data from YouTube API |
| `transcripts.json` | Transcript text for top videos |
| `analysis.json` | Analysis metadata |
| `report_brief.md` | Full markdown trend analysis (input to Gamma or PDF) |
| `report.pdf` | PDF output (only present if PDF format was chosen) |

`outputs/` is gitignored — all run data stays local.

---

## Improvements Log
- 2026-03-30: Initial generic build. Parameterized from the Biz Ignite specific version.
