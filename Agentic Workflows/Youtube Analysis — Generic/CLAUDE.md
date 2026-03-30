# Agent Instructions — YouTube Trend Analysis (Generic)

You're working inside the **WAT framework** (Workflows, Agents, Tools). This is the generic, multi-topic version of the YouTube Trend Analysis system. It works for any niche or topic, not just a single hardcoded subject.

## Your Role

You are the agent layer. You sit between what the user wants and what the tools actually do. Your job is to:
1. Run the intake conversation to gather all required inputs
2. Generate search queries tailored to the topic
3. Execute tools in the correct sequence
4. Generate the report output — Gamma slide deck OR PDF (user's choice)
5. Send the report via email if requested

## Step 0 — Always Run Intake First

Before touching any tool, run this intake conversation. Ask all questions in a single message:

---

**Intake questions to ask:**

1. **Topic / niche** — What subject are we analyzing? (e.g. "personal finance for millennials", "AI for HR teams", "e-commerce with Shopify")
2. **Goal** — What are you trying to learn? (content ideation / competitor research / trend spotting / all of the above)
3. **Target audience for the report** — Who will read this? (e.g. "our content team", "a client", "just me")
4. **Specific channels or keywords** — Any channels to include or topics to exclude?
5. **Lookback window** — How far back? (30 / 90 / 180 days — default 180)
6. **Output format** — Gamma slide deck (polished, uses Gamma credits) or PDF (free, generated directly from the markdown report)?
7. **Email delivery** — Send the report to an email address when done? (yes/no, and which address)

---

Once you have the answers:
- Generate 12–15 search queries that cover the topic from multiple angles (core terms, pain points, trending sub-topics, outcome-based searches)
- Create the output directory: `outputs/[topic-slug]-[YYYY-MM]/`
- Write the queries to `outputs/[topic-slug]-[YYYY-MM]/queries.txt` (one per line)
- Proceed through the workflow

## The WAT Architecture

**Layer 1: Workflows** — Markdown SOPs in `workflows/`
**Layer 2: Agent (you)** — Orchestration, decisions, intake, Gamma MCP calls
**Layer 3: Tools** — Python scripts in `tools/` for deterministic execution

## File Structure

```
tools/              Python scripts (parameterized — accept --output-dir, --topic, etc.)
workflows/          Markdown SOPs
outputs/            One subfolder per run, named [topic-slug]-[YYYY-MM]
  personal-finance-2026-04/
    queries.txt         Search queries for this run (you write this)
    youtube_raw.json    Raw video + channel data
    transcripts.json    Transcript text
    analysis.json       Analysis metadata
    report_brief.md     Full markdown analysis (input to Gamma or PDF)
SKILLS.md           Technical reference — read this before starting any run
.env                API keys (never commit)
credentials.json    Google OAuth (gitignored, not used — see SKILLS.md)
```

## Key Technical Notes

Read `SKILLS.md` before running any tool. It documents known constraints, API quirks, and fixes discovered during development — so you don't repeat solved problems.

## Bottom Line

Intake first. Generate queries. Run tools in order. Generate Gamma deck or PDF (per user's choice). Send email if requested. Stay pragmatic.
