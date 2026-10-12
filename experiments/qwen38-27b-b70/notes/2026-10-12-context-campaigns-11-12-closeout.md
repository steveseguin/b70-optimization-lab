# Context campaigns 11 and 12 (in-place notes in the proxy) — closeout

<!-- campaign-closeout -->

The running record, with every table and the preregistrations, is the lab note
[2026-10-10-context-16k-baseline.md](2026-10-10-context-16k-baseline.md), sections "Campaign 11 ..." and
"Campaign 12 ...". This page is the short form. The lane is not finished; these two campaigns are.

## Question and identity

Can the fast form of the keeper (in-place notes: the notes call is the live conversation plus one message, the reply
holds only what changed, the harness or proxy checks and applies it) be moved out of the test harness into the
proxy `tools/ctxkeeper`, for an agent that sends its whole history and manages nothing, without losing answers or
speed? And does a rule that names nothing it covers separate notes from retrieval?

- Model and serving: Qwen3.8-27B FP8 (official weights), two Arc Pro B70 (TP2), vLLM image
  `neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride`, native MTP 5, exact prefix cache,
  `--max-model-len 262144`, 16-bit KV; guard floor 1.6 GiB. Serving is lossless; what is measured here is the
  agent's answers, not token identity.
- Workload: sparse prose ledger streams (`make_sparse_prose_tasks.py`), 32K live window: rules 240K seeds 0 and 1
  (39 and 46 questions), 1M seeds 0 and 1 (228 and 222), `crule` 240K seeds 0 and 1 (a rule by condition), hard
  240K seed 1 (pronouns, values that depend on other counters).
- Dates: 2026-10-12 03:12 to 06:03 (campaign 11) and 06:26 to 10:47 (campaign 12), host `steve-TURIND8-2L2T`.
- Arms are code states (header of `scripts/context/second-comparison.sh`): proxy X32i, X32m, X32n, X32n2, X32p;
  harness N32k, N32m, N32n, N32nr; retrieval only R32b.

## Outcome

Accepted: the proxy with in-place notes replaces its full-rewrite form. At 1M it is within two answers of the
harness arm it was built from, and as fast.

| arm | 240K seed 0 (39) | 240K seed 1 (46) | 1M seed 0 (228) |
| --- | ---: | ---: | ---: |
| proxy, full rewrite (X32b, campaign 9) | 39 in 17.0 min | 44 in 18.0 min | 222 in 95 min |
| proxy, in-place, first build (X32m) | 39 in 10.2 min | 46 in 13.1 min | 216 in 76 min |
| proxy, in-place, after the first 1M run's fixes (X32n2) | 39 in 8.8 min | 46 in 9.7 min | **220 in 53 min** (bar: 220 in under 70) |
| proxy, in-place, code state p (X32p) | 39 in 8.5 min | 46 in 9.4 min | **226 in 50 min** |
| harness keeper, in-place (N32u, campaigns 10 and 10b) | 39 in 9.9 min | 46 in 10.0 min | 228 in 50 min |

Also measured:
- A rule that names nothing (`crule`): keeper 16 of 16 governed questions over two seeds, retrieval alone 0 of 16.
- Harness keeper on the second 1M stream (N32n): 210 of 222 in 50 minutes; 438 of 450 over the two streams.
- Hard stream seed 1, keeper with retrieval (N32nr): 46 of 49 in 23 minutes; the partner run without retrieval
  did not finish (stopped by hand at item 78).
- X32n (an intermediate build): 14 of 39 and 45 of 46; see "What failed".

Scope of the quality claim: one model, one machine, one synthetic task family, one run per cell.

## What worked

- In-place notes in the proxy: the notes request is the previous upstream view without the newest exchange plus
  one instruction (same tool list, `tool_choice` none); about 90 % of its prompt tokens come from the server's
  prefix cache; the newest exchange stays in view. Evidence: `data/2026-10-12-context-campaign11-12/proxy/*/`
  (every notes reply in `events.jsonl`, every NOTES version in `notes-history.jsonl`, audits against the true
  ledger).
- Checks on a changes-only reply, each added after an audited error: lines counted and followed by their parts,
  a change noted before read as no change, amounts in working must be stated for the thing, a questioned reply
  never falls back to the full rewrite, a line whose number the turns do not state is left out.
- For the search tool: hits labelled with their item; the searches of a turn that ended empty are carried into the
  next request; (code state p) one numbering only and the nearest matches first.
- Process: replaying saved replies through new checks before a run (it predicted the fall from 33 to 9 questions);
  a read-only review by a second model instance while the cards are busy; a sampler of the server's own prefill and
  decode seconds per run.
- The end-of-run guard events are explained: `summarize_results.py` held 1.7 GB of snapshots at once. Fixed.

## What failed or remains uncertain

- X32m at 1M (216): six answers blank because proxy-answered searches were lost when a turn ended empty; six wrong
  because hits carried message numbers. Fixed in X32n2.
- X32n (14/39, 45/46): a questioned notes reply got no usable answer and the cut fell back to the full rewrite,
  which lost a change on one seed and on the other wrote a rule that restated the task's opening message; recited at
  the final item it led the model to overwrite a file holding 25 right answers. Fixed in X32n2 (the first reply
  stands).
- X32n2 at 1M (220): seven of eight misses from one confusion, message numbers against item numbers in the search
  tool. Fixed in code state p (X32p: 226, every earlier-value question right).
- X32p at 1M (226): its NOTES had five counters wrong at some point (X32n2: two), two of them because the new
  rule "a line whose number the turns do not state is left out" took out lines that were right but written in a
  form the checker could not follow. Corrected after the run (commit `7ff735ef1`), not yet run.
- N32n on the second 1M stream (210/222): an ordinary cut moved an open question item out of view (seven blank).
  Fixed in the repo after the run (commits `d6d99188d`, `69a86c64c`), not yet run.
- Not caught by any check: a change noted with the wrong sign, a set noted as a change by the same number (about
  one line in 75 notes calls).
- The hard stream is slow with the day's stricter checks (23 minutes; a run hung). The fix (an amount may be
  another thing's value) is in code state p and has not been run on that stream.
- One guard event (campaign 10, after an interrupted retrieval run) is still unexplained.
- Everything here is the synthetic ledger. The real-code task (`make_repair_tasks.py`) is built and reviewed, not
  yet screened or run.

## Evidence and patches

- Lab note: [2026-10-10-context-16k-baseline.md](2026-10-10-context-16k-baseline.md).
- Evidence folder: [`../data/2026-10-12-context-campaign11-12/`](../data/2026-10-12-context-campaign11-12/)
  (logs, queues, runners, tables, audits, per-run counters, the proxy's notes history and events; `collect.sh`
  rebuilds it from the raw results under `/mnt/fast-ai/bench-results/context-longrun-2026101{0,1,2}/`, which are
  not in Git).
- Code: `tools/ctxkeeper/` (proxy, tests, README), `scripts/context/clm_keeper.py`, `recall.py`,
  `summarize_results.py`, `proxy_notes_audit.py`, `make_repair_tasks.py`.
- Program charter: [`docs/long-horizon-context-program.md`](../../../docs/long-horizon-context-program.md).

## When to revisit

Next steps, in order: the proxy and the harness with the open-question fix on the second 1M stream; the hard
stream with code state p; the real-code task (proxy against a sliding window and summary compaction); then the
proxy under a real agent program, which is the owner's choice to make.
