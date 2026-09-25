# Working conventions for this repo

Project structure, data sources, and the cluster-spec concept are documented in
`README.md`; current research status and open items are in `BACKLOG.md`. Read
both before starting work. This file covers *how* to work in this repo, not
*what* it contains.

## Source of truth

`origin/main` on GitHub is the canonical state — not any one local checkout.
The daily GitHub Action (`.github/workflows/daily.yml`, 05:00 CEST) scrapes
and commits `data/watches.db` directly to `origin/main`. A local session that
sits on unpushed commits for a while will diverge from that automated commit
stream (binary conflicts on `data/watches.db` are the main risk). Push
promptly rather than letting local work sit uncommitted-to-origin for long.

The weekly local backup (`scripts/backup_data.py`, Sunday 18:00 scheduled
task) copies `data/watches.db` + master data + CSV exports to `data/backup/`.
This is a plain file copy, independent of git — don't route it through git.

## Git workflow

- Commit locally with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Default: let the user push from their own terminal. Only push directly (or
  open a PR) when the user explicitly asks for that in the current turn — it
  is not a standing permission from one occasion to the next.
- Never force-push `main`. If local and `origin/main` have diverged, prefer
  `git rebase origin/main` over a merge, and resolve any `data/watches.db`
  conflict by keeping `origin`'s copy (`git checkout --ours data/watches.db`)
  — it's always the freshest scraped data, and scrape-time overrides (see
  below) reapply themselves on the next daily run regardless of which
  historical DB blob won a given commit.

## Dashboard (Claude Artifact)

The dashboard is published as a private Claude Artifact, always at the same
URL: `https://claude.ai/code/artifact/6d3dcd76-7a47-460e-b0b8-ac3e90ed517a`.
Favicon (⌚) is already set — don't repass it on redeploy.

Rebuild before every publish:
```
python3 scripts/export_dashboard_data.py && python3 scripts/build_dashboard.py
```
Then `Artifact action="read"` on that URL *immediately* before
`action="publish"` — a scheduled cloud routine republishes this dashboard
automatically once a day (~04:00 UTC), so the live version can be newer than
your last read. An `artifact-changed` notification about this dashboard while
you aren't actively publishing is expected background noise, not an error.

## Cluster-spec research

`data/cluster_specs_*.json` (one file per brand) supplies case/bezel/bracelet/
size per reference number, used to build genuinely-comparable cluster labels
in place of the too-coarse `model_line`. When researching a brand's missing
references:

- **One agent, one brand, sequential. Never spawn sub-agents, never run
  multiple brand-research agents in parallel.** (Hard rule, from a past
  rate-limit incident.)
- **Gap is fine, wrong guess is not.** Omit a field, or skip a reference
  entirely, rather than guess. A skipped/ambiguous reference is a fine
  outcome to report back.
- The database sometimes stores a short/garbled fragment of a reference
  (extracted by the scraper's regex from a longer real reference elsewhere in
  the title). Research the full real reference to identify the watch, but key
  the JSON entry to the exact fragment string stored in the DB — that's what
  the lookup in `export_dashboard_data.py` matches against.
- Match each file's existing vocabulary exactly (case/bracelet material terms
  are brand-specific and already established — check the file before adding
  a new term).

## Override layers (three, each at a different point in the pipeline)

- `data/manual_overrides.json` + `scrapers/overrides.py` — applied at scrape
  time (`run.py`), corrects raw scraped fields (`model_line`,
  `reference_number`) or excludes non-watch listings (spare parts). Persists
  across daily scrapes automatically since it's applied on every run.
- `data/cluster_specs_*.json` — applied at export time, supplies case/bezel/
  bracelet/size (see above).
- `data/color_variants_rolex.json` (reference-level) and
  `data/color_overrides_listings.json` (listing-level, from user-confirmed
  photo review) — applied at export time, supply dial/bezel color.
  Listing-level overrides win over reference-level research over raw scraped
  text; `color_source` in the exported data records which one applied.

These three are independent — don't conflate a scrape-time fix with an
export-time one when deciding where a correction belongs.
