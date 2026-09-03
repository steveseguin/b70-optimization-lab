# Efficiency audit protocol

Purpose: a recurring, read-mostly observer that measures how fast the lab
turns GPU time and agent time into published, reproducible speed recipes, and
proposes the few process changes that would make the next week faster. It is
forward-looking: every finding must generalize to future scenarios, not only
explain one past lane.

The auditor never launches GPU work, never edits published recipes, results,
preregistrations, or `CURRENT.md`, and never merges. It writes one dated
report under `audits/efficiency/` and opens a pull request with it (branch
`audit/efficiency-<date>`); if it cannot push, the report is the run's final
message.

## Inputs (all in the repository)

1. `scripts/efficiency-audit-metrics.py --days 7 --out <json> --markdown <md>`
   for the fixed measuring stick: commits by author, campaigns with
   preregistration-to-result latency and outcome class, arms per lane,
   infrastructure-event mentions, and rule signals.
2. `AGENTS.md` section "Diagnosis And Campaign Speed Rules" (the rules the
   audit checks compliance against), `experiments/*/DO-NOT-REPEAT.md`,
   `CURRENT.md`, and the window's notes under `experiments/*/notes/`.
3. Git history for the window (`git log --since`), including commit subjects
   and timestamps, to reconstruct the sequence of arms and the wall-clock
   between them.

## What to measure and report

- **Throughput of the lab**: campaigns started, campaigns with a result,
  accepted / rejected / aborted-by-infrastructure counts per lane, and the
  median and worst preregistration-to-result latency.
- **Where time went**: the three longest stretches of consecutive arms that
  ended without an accepted result, with the hypothesis each was chasing and
  which rule, if any, would have shortened it.
- **Rule compliance** (one line each, with the offending campaign ids):
  census before bisection; oracle regenerated when the kernel changed; no
  speed verdict from one server; whole campaign in one runner; journal
  fast-fail on faults; stop at the first passing gate; read-only work
  delegated while GPUs were busy; one lane per host.
- **Infrastructure tax**: GPU faults, resets, freezes, reboots, and the GPU
  time lost to replays because of them.
- **Distance to the goal**: for each active lane, what is published, what is
  qualified but unpublished, and the single gate that stands between the
  current candidate and publication.
- **Token and attention cost** where visible: number of preregistrations and
  notes written per accepted result, and any duplicated artifacts (two
  scripts or notes that do the same thing).

## Output format

`audits/efficiency/YYYY-MM-DD.md` with sections in this order: Verdict (one
paragraph: is the lab getting faster or slower, and why), Metrics table,
Where the week went, Rule compliance, Top three changes (each: the change,
the evidence, the expected saving, how it generalizes to future lanes), and
Checks performed. Under 900 words. Cite file paths and campaign ids; never
cite a number the metrics script or a committed file does not contain.

Reports are advice. The lab adopts a proposed change by editing `AGENTS.md`
in a normal commit; the auditor does not edit `AGENTS.md` itself.
