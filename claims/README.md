# Claims registry — who claimed what, and what the lab verified

One JSON file per accepted performance claim. This registry records the exact
recipe identity, evidence, submitter, and dated lab outcome. It does not make an
outside repository authoritative for a lab-developed lane.

## Why this exists

- **Claimed vs verified, side by side.** A claim enters with the number its
  author measured. It leaves the queue only when the lab re-runs it and records
  its own number next to the original.
- **Credit that survives.** A concrete contributed patch or recipe keeps its
  author and pinned source identity. Broad collections of numbers are not
  imported as claims merely because they mention B70.
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

Accepted claims are not silently deleted. Refuted and stale claims stay in the
registry with their evidence — a negative result is still a result. Intake
records created without an accepted submission or runnable evidence may be
removed during review; Git history preserves that correction.

Confirmation requires the same model/checkpoint, quantization, runtime and
patch identity, GPU topology, metric, and quality gate. Similar throughput on
a different lab lane is not confirmation and must be recorded separately.

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
| `upstream` | for a concrete imported contribution | `{repo, author}` — pin and credit the exact source |
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
through the lifecycle as the lab re-runs it. Unverified claim files do not make
the landing-page tables. Public highlights need a runnable in-repo packet and a
matching lab evidence identity.

## The bench queue

Claims in `submitted`/`queued` are the lab's testing backlog — including new
models the lab wants to bench and optimize on the growing B70 fleet. Want a
model tested? File it as a claim with your number (or the vendor's), and it
enters the queue in the open.
