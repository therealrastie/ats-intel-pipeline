# ATS Intelligence Pipeline

Autonomous job-market monitoring and document generation. Zero servers, zero manual searching.

**What it does:** polls four ATS platforms (Greenhouse, Lever, Ashby, Workday) on a GitHub Actions cron schedule, scores new postings against a target profile, and generates role-tailored resumes from a master YAML using the Claude API.

## Architecture

```
GitHub Actions (cron, every 6h)
        |
   jobscan.py ──> Greenhouse / Lever / Ashby / Workday public job APIs
        |            (per-company adapters, no scraping, no auth)
   score & filter (keywords, seniority, location)
        |
   matches.json  ──commit──>  repo (diff = new postings)
        |
   tailor.py ──> Claude API
        |            master_resume.yaml (single source of truth)
        |            job description (fetched per match)
        v
   out/<company>-<role>.md   (tailored resume, ready for review)
```

## Design principles

- **Boring, reliable parts.** Cron, YAML, JSON, one well-scoped LLM call. The LLM is used only where judgment is needed (tailoring), never for orchestration.
- **Single source of truth.** All career facts live in `master_resume.yaml`. The tailoring engine may reorder, emphasize, and rephrase. It is instructed to never invent facts.
- **Zero-touch.** Runs unattended. New matches show up as commits; tailored documents show up as files.

## Outcomes

- Per-application tailoring: [YOUR MEASURED BASELINE] minutes manual → ~2 minutes of review
- Continuous coverage of [N] target companies with no missed postings
- Cost: [YOUR MEASURED FIGURE] per month in API + $0 infrastructure (GitHub Actions free tier)

## Setup

1. Fork this repo.
2. Copy `master_resume.example.yaml` to `master_resume.yaml` and fill in your profile.
3. Edit `targets.yaml` with the companies and role keywords you care about.
4. Add `ANTHROPIC_API_KEY` as a repository secret.
5. Enable Actions. The scan runs every 6 hours; trigger manually with `workflow_dispatch` to test.

## Honest-use note

The tailoring prompt hard-constrains the model to the facts in your master YAML. Review every generated document before sending it anywhere. This tool compresses effort; it does not replace your judgment or your integrity.

MIT License.
