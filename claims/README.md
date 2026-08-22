# Claims registry — who claimed what, and what the lab verified

One JSON file per performance claim. This is the canonical record behind the
tables on the site: every "claimed vs verified" number, who submitted it, which
upstream repo it came from, and the full dated history of what happened to it.

## Why this exists

- **Claimed vs verified, side by side.** A claim enters with the number its
  author measured. It leaves the queue only when the lab re-runs it and records
  its own number next to the original.
- **Credit that survives.** Every claim names its submitter and, when pulled
  from someone's repo, the upstream repo and author. Contributors can point at
  a permanent record of what they added and how it held up over time.
- **Progress over time.** `history[]` appends an event at every state change,
  so a lane's arc — submitted → reproduced → confirmed, or adjusted, or
  refuted — is visible instead of silently edited.
- **Automation-ready.** `tools/validate-claims.py` enforces the schema on every
  PR today; the same files are the input for automatic claim review and, later,
  automatic re-benchmarking on the lab's B70 fleet.

## Lifecycle

```
submitted ──► queued ──► reproducing ──► confirmed
                                       ├─► confirmed-adjusted   (real, but the lab measures a different number)
                                       ├─► refuted              (cannot be reproduced; evidence recorded, not deleted)
                                       └─► stale                (was true; software or model moved on)
lab-verified   (claim originates from the lab itself; number is the lab's own measurement)
```

Nothing is deleted. Refuted and stale claims stay in the registry with their
evidence — a negative result is still a result.

## Schema (one file per claim, `claims/<id>.json`)

| field | required | meaning |
|---|---|---|
| `id` | yes | filename without `.json`; lowercase, hyphenated |
| `model` | yes | model name as shown on the site |
| `recipe` | yes | `{engine, quant, speedup, cards, tp}` — `speedup` may be `null` |
| `claimed.tok_s` | yes | the number the author reported |
| `claimed.metric` | yes | how it was measured, in plain words |
| `claimed.date` | yes | `YYYY-MM` or `YYYY-MM-DD` |
| `claimed.by` | yes | submitter handle (use `"lab"` for the lab's own claims) |
| `submitter.url` | for outside claims | submitter's profile/home link |
| `upstream` | when pulled from a repo | `{repo, author}` — full credit to the source |
| `status` | yes | one of the lifecycle states above |
| `verification` | for confirmed/adjusted/refuted/lab-verified | `{tok_s, metric, date, evidence}` — `evidence` is a repo path that MUST exist |
| `history[]` | yes | `{date, event}` per state change, oldest first |

## Submitting a claim

Two ways in:

- **Issue:** open a [result report](https://github.com/steveseguin/b70-optimization-lab/issues/new?template=result.yml)
  with the full evidence checklist. A maintainer converts qualifying reports
  into a claim file crediting you.
- **PR:** add one file under `claims/` plus your runnable assets under
  `community/<handle>-<model>-<engine>/` (see CONTRIBUTING.md).

The validator runs on every PR touching `claims/`; a maintainer moves the claim
through the lifecycle as the lab re-runs it. Bench numbers without a claim file
don't make the site tables.

## The bench queue

Claims in `submitted`/`queued` are the lab's testing backlog — including new
models the lab wants to bench and optimize on the growing B70 fleet. Want a
model tested? File it as a claim with your number (or the vendor's), and it
enters the queue in the open.
