#!/usr/bin/env python3
"""tailor.py: generate a role-tailored resume from the master YAML.

Usage:
    python tailor.py <match_index>          # tailor for the Nth match in matches.json
    python tailor.py --url <job_url>        # tailor for an arbitrary posting URL

The model receives two things: the master resume (source of truth) and the
job description. It is hard-constrained to never invent facts. Every output
is a draft for human review, not a finished document.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import requests
import yaml
from anthropic import Anthropic

MODEL = "claude-sonnet-4-5"

SYSTEM = """You are a resume tailoring engine.

Hard rules:
1. Use ONLY facts present in the master resume YAML. Never invent employers,
   dates, titles, metrics, tools, or accomplishments. If the job asks for
   something the candidate does not have, do not claim it.
2. You MAY reorder sections, select the most relevant bullets, and rephrase
   bullets for impact and keyword alignment with the job description.
3. Output clean Markdown only: name and contact header, summary, skills,
   experience, certifications, education. No commentary, no preamble.
4. Keep it to one page equivalent (about 450 to 550 words)."""


def fetch_job_text(url: str) -> str:
    r = requests.get(url, timeout=20, headers={"User-Agent": "ats-intel-pipeline"})
    r.raise_for_status()
    # crude but sufficient: strip tags, collapse whitespace
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)[:12000]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("match_index", nargs="?", type=int)
    ap.add_argument("--url")
    args = ap.parse_args()

    master = Path("master_resume.yaml")
    if not master.exists():
        sys.exit("master_resume.yaml not found. Copy the example file and fill it in.")
    resume_yaml = master.read_text()

    if args.url:
        url, label = args.url, "custom"
    else:
        data = json.loads(Path("matches.json").read_text())
        m = data["matches"][args.match_index or 0]
        url = m["url"]
        label = f"{m['company']}-{m['title']}"

    job_text = fetch_job_text(url)

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"MASTER RESUME (source of truth):\n```yaml\n{resume_yaml}\n```\n\n"
                f"JOB POSTING:\n{job_text}\n\n"
                "Produce the tailored resume now."
            ),
        }],
    )
    out = "".join(b.text for b in msg.content if b.type == "text")

    Path("out").mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:80]
    path = Path("out") / f"{slug}.md"
    path.write_text(out)
    print(f"wrote {path}. Review before sending: the model tailors, you verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
