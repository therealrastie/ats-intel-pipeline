#!/usr/bin/env python3
"""jobscan.py: poll ATS platforms, score postings, write matches.json.

Adapters use each platform's public job-board JSON endpoints. No scraping,
no authentication, no rate abuse: one request per company per run.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

UA = {"User-Agent": "ats-intel-pipeline (personal job search tool)"}
TIMEOUT = 20


def fetch_greenhouse(board: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [
        {"title": j["title"], "url": j["absolute_url"],
         "location": (j.get("location") or {}).get("name", "")}
        for j in r.json().get("jobs", [])
    ]


def fetch_lever(board: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{board}?mode=json"
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [
        {"title": j["text"], "url": j["hostedUrl"],
         "location": (j.get("categories") or {}).get("location", "")}
        for j in r.json()
    ]


def fetch_ashby(board: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [
        {"title": j["title"], "url": j["jobUrl"], "location": j.get("location", "")}
        for j in r.json().get("jobs", [])
    ]


def fetch_workday(host: str, site: str) -> list[dict]:
    tenant = host.split(".")[0]
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
    out = []
    while True:
        r = requests.post(url, json=payload, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        for j in data.get("jobPostings", []):
            out.append({
                "title": j.get("title", ""),
                "url": f"https://{host}/{site}{j.get('externalPath', '')}",
                "location": j.get("locationsText", ""),
            })
        payload["offset"] += payload["limit"]
        if payload["offset"] >= data.get("total", 0) or payload["offset"] > 400:
            return out


def score(job: dict, cfg: dict) -> int:
    """Simple, explainable scoring. Deliberately not an LLM call:
    orchestration stays deterministic; the LLM is saved for tailoring."""
    text = f"{job['title']} {job['location']}".lower()
    if any(x in text for x in cfg.get("exclude", [])):
        return -1
    s = sum(1 for k in cfg.get("keywords", []) if k in text)
    if any(loc in text for loc in cfg.get("locations", [])):
        s += 1
    return s


def main() -> int:
    cfg = yaml.safe_load(Path("targets.yaml").read_text())
    matches, errors = [], []

    for co in cfg["companies"]:
        try:
            if co["ats"] == "greenhouse":
                jobs = fetch_greenhouse(co["board"])
            elif co["ats"] == "lever":
                jobs = fetch_lever(co["board"])
            elif co["ats"] == "ashby":
                jobs = fetch_ashby(co["board"])
            elif co["ats"] == "workday":
                jobs = fetch_workday(co["workday_host"], co.get("workday_site", "External"))
            else:
                continue
        except Exception as e:  # one bad board never kills the run
            errors.append(f"{co['name']}: {e}")
            continue

        for job in jobs:
            s = score(job, cfg)
            if s >= cfg.get("min_score", 2):
                matches.append({**job, "company": co["name"], "score": s})

    matches.sort(key=lambda m: -m["score"])
    Path("matches.json").write_text(json.dumps({
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "matches": matches,
        "errors": errors,
    }, indent=2))
    print(f"{len(matches)} matches, {len(errors)} board errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
