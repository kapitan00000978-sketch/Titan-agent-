---
name: research-ops
description: Multi-hop research playbook — find sources, verify claims, cite everything.
keywords: research, sources, citations, verify, facts, news, investigate
---

# Research Ops

Follow this playbook whenever the task is research, fact-finding, news, or an
investigation.

## Steps
1. PLAN the angles: break the topic into 2–4 concrete sub-questions.
2. SEARCH each angle with `web_search` (different phrasing per angle).
3. PREFER PRIMARY sources: official docs, papers, reputable outlets. Scrape the
   actual page with `scrape_webpage` when a snippet is too thin.
4. CROSS-CHECK: if two sources disagree, say so explicitly — do not smooth over
   conflicts. Flag recency: prefer information updated within the last year.
5. CITE: every claim in the final answer must point at a URL you actually
   retrieved. Never invent URLs.
6. GAP HONESTY: if evidence is thin, say "evidence is limited" rather than
   padding with guesses.

## Output shape
Start the final answer with a **Summary** (3–4 bullets), then **Findings** with
per-claim citations, then **Sources** (list of URLs), then **Known gaps**.

## Efficiency
Reuse one search result set across questions where possible. Do not re-scrape
the same page twice.