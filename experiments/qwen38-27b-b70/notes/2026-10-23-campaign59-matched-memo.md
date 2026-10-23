# Campaign 59: seed 2 with fixed sandbox metadata, memo off/on

Registered October 23, 09:36 EDT, before either GPU run. This follows the
[campaign 58 failure and confound](2026-10-23-campaign58-closeout.md).

## Question and controlled change

Does the memo preserve all model-visible text and quality when seed 2's opening directory listing
is held fixed? The first differing c55/c58 input is `/app/..`'s mtime. The fixture sets only the
sandbox `/` directory mtime to **1792687500 = 2026-10-22 16:45:00 UTC**, after normal setup and before
the first model call. This reproduces c55's observed minute, chosen to test that specific confound,
not selected by testing different dates. The timestamp does not encode task answers. All original
task files, instructions, stream, tool outputs and graders are preserved; outputs are never filtered.
This does not freeze arbitrary commands such as `date` or all filesystem metadata. Any remaining
observed input differences must be reported and invalidate a claim of matched input.

Two stages, each a fresh server, one unattended runner:

| Stage | Run | Seed | Memo | Fixture | Model/keeper |
| --- | --- | --- | --- | --- | --- |
| Control | c59a | 2 | COUNT_MEMO=0 | Same fixed root mtime | c58 server, K32V, ctxkeeper 1.3.0 |
| Candidate | c59b | 2 | COUNT_MEMO=1 | Same fixed root mtime | Identical |

`PLAIN_AGENT_KIND=plain-stable-fixture` selects a separate PlainAgent subclass. It records and checks
the applied sandbox timestamp in `agent/stable-fixture.json`. Normal `plain` is unchanged. Model
thinking stays on. Host, full-precision KV, MTP5, piece 832, exact prefix cache, lean client, task,
per-stage 14,400 s cap and all proxy settings match c58. No other work during the GPU runs. No resident
server restored; `RESTORE=0`. This is an explicitly modified benchmark environment for a controlled
comparison, not a retrospective repair of campaign 58.

## Predictions and decisions

- Both initial tool observations match c55 exactly. Both complete all 423 questions, nonvoid.
- c59a and c59b have identical full archived text sequences, NOTES text sequences and answer maps.
  Stronger prediction: both reproduce c55 seed 2's 152 NOTES versions and 420/423 with two audit flags,
  both audits PASS. A different but matching pair is evidence of memo identity only; report the
  missed c55 prediction and judge quality independently.
- Candidate client wall 79–86 min vs control 90–98 min; at least 8% lower. Main+notes model seconds
  differ by at most 5%. Between-step residual at most 350 s in the candidate vs 700–1,000 s control.
  These are c58-informed new predictions; c58's 150 s miss remains a miss.
- Any incomplete run, unexpected initial observation, fault or unconfirmed server shutdown stops the
  chain without another launch. An otherwise complete control with a failed quality audit may still
  run its paired candidate to test memo identity; neither quality failure is waived.
- Memo stays default off during the experiment. Restore it only after reviewing identical-input/output
  evidence and passing quality audits. A mismatch keeps it off and triggers first-divergence analysis.
  No public wall update is automatic, and no external publication is performed by this runner.

## CPU checks and operation

Five unit tests verify required explicit timestamp, sandbox-only command construction, setup order,
receipt validation and failure handling. Two real Harbor jobs against a CPU fake server, memo off/on,
produce identical 26 request bodies, trajectory, usage, grader output and 28 snapshots. Both sandbox
receipts confirm the target mtime. These are wiring checks, not model-quality measurements.
[Preflight receipts](../data/2026-10-23-campaign59-preflight/).

Runner: [run_campaign59.py](../scripts/context/run_campaign59.py), built on the existing campaign runner.
It refuses existing run paths, records each stage's logs, checks kernel fault signatures and saved
completion/shutdown/fixture evidence, runs the unchanged audit after each server is down, then compares
the pair and writes the time split. It never commits, pushes, retries or changes defaults.

Launch from `scripts/context` in unit `ctx-campaign59`:

```bash
systemd-run --user --unit=ctx-campaign59 --collect \
  -p WorkingDirectory=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context \
  -E SUDO_ASKPASS=/home/steve/.askpass.sh \
  python3 run_campaign59.py
```

Status/results: `/mnt/fast-ai/bench-results/context-longrun-20261016/campaign59-control/`;
raw trials and proxy state under the sibling `runs/c59{a,b}` and `proxy-state/c59{a,b}-*` directories.
Read the opening observation after startup and the first NOTES version before relying on the long run.
