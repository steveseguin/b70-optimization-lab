# Retrieval batching: completed-run review and prospective controls

2026-10-07. CPU/read-only analysis; this file is the only output. No current history-study result, trace, call log or intermediate model output was inspected. No runtime changes or operational actions were taken.

## Finding

The completed structured-state trials spend most of their time answering, usually through many retrieval-directed model turns. This makes bounded bulk fetch a credible next interface experiment. It does **not** establish that HTTP or local fetch latency dominates: each measured request includes model inference, reasoning and possible saved answers. The stronger short-document control is simply providing the complete original source. That control fits the authored semantic/temporal documents but cannot fit the existing sparse streams under the same byte limit.

No measured batching speedup exists. Neither fewer requests nor CPU correctness establishes maintained model quality. Existing ingestion defects also survive a better retrieval interface.

## Measurement definitions and evidence

Read only the completed semantic, sparse screen and sparse replication diagnostic roots listed below. For every native result, parsed `calls.jsonl`, `answer_protocol.cache` and, where present, `retrieval.jsonl`. `answer seconds` sums call `seconds` for phase `answer`; ingestion sums other phases. These are client request elapsed times, not GPU-only or wire-only timings. `wall` is native end-to-end trial elapsed. Requested actions are parsed from each answer response; a response may save answers as well as request retrieval. Accepted distinct retrievals count canonical cache keys; response counts include successful repeats. All inspected retrieval responses were successful, with zero logged retrieval errors. All 575 calls across the three campaigns independently had integer `cached_tokens=0` in raw usage (265/155/155).

### Short semantic documents: totals over 12 trials per arm

| Arm | Wall s | Ingest s | Answer s (% wall) | Answer calls | Requested fetch/search/update/submit | Accepted distinct fetch/search | Answers correct |
|---|---:|---:|---:|---:|---|---|---:|
| summary | 113.2 | 49.8 | 62.1 (54.9%) | 12 | 0/0/0/12 | 0/0 | 84/84 |
| archive | 353.0 | 29.1 | 321.9 (91.2%) | 55 | 38/4/1/12 | 38/4 | 82/84 |
| quoted | 381.4 | 48.6 | 330.6 (86.7%) | 54 | 37/5/0/12 | 37/5 | 84/84 |

Every archive and quoted trial retrieved evidence; none of the summary trials did. Archive/quoted each accepted 42 distinct retrievals, with no repeated retrieval responses. Their fetch/search-directed calls used 225.5/242.3 seconds, respectively: 70.1%/73.3% of answer-phase time. The 12 final submit calls still cost 87.1/88.3 seconds. Summary's 84/84 answers are an observed result on this small diagnostic, not proof of lossless long-stream memory. Archive's 82/84 means its elapsed cannot be promoted as an exact-output comparison.

### Sparse streams: each trial, including failures of quality

`F/S/U/T` = requested fetch/search/update/submit calls. `Distinct F/S` counts successful unique queries. `Responses (repeats)` includes successful cached answers. Times are seconds.

| Run/case | Arm | Wall | Ingest | Answer (% wall) | Answer calls F/S/U/T | Distinct F/S | Responses (repeats) | Final / checkpoints |
|---|---|---:|---:|---:|---|---|---|---|
| screen/n8-seed83 | archive | 316.8 | 18.7 | 297.4 (93.9%) | 20: 17/2/0/1 | 14/2 | 19 (3) | 23/24 / exact |
| screen/n8-seed83 | quoted | 349.1 | 29.1 | 319.3 (91.4%) | 21: 16/4/0/1 | 14/4 | 20 (2) | 24/24 / exact |
| screen/n128-seed83 | quoted | 397.3 | 88.0 | 308.4 (77.6%) | 16: 8/6/1/1 | 8/5 | 14 (1) | 24/24 / exact |
| screen/n128-seed83 | archive | 507.5 | 209.9 | 296.7 (58.5%) | 16: 4/9/2/1 | 4/8 | 13 (1) | 24/24 / exact |
| repeat/n128-seed83 | archive | 506.6 | 209.9 | 295.9 (58.4%) | 16: 4/9/2/1 | 4/8 | 13 (1) | 24/24 / exact |
| repeat/n128-seed83 | quoted | 397.1 | 88.1 | 308.1 (77.6%) | 16: 8/6/1/1 | 8/5 | 14 (1) | 24/24 / exact |
| repeat/n128-seed97-dispatch | quoted | 362.6 | 96.8 | 264.9 (73.1%) | 13: 8/3/1/1 | 8/3 | 11 (0) | 24/24 / exact |
| repeat/n128-seed97-dispatch | archive | 507.1 | 227.4 | 278.9 (55.0%) | 14: 9/3/1/1 | 9/3 | 12 (0) | 24/24 / inexact |

Fetch/search-directed requests used 72.7–92.8% of these answer-phase seconds. Fetch alone was not always the main action: the report128 archive used four fetches versus nine searches, spending 56.4 versus 159.3 seconds in the original screen. A bulk-fetch-only change may therefore leave much of its work unchanged. Search batching would be a separate treatment and is not proposed here.

The repeated report128 pair isolates the already observed saving: initialization was almost equal (archive 53.6 s, quoted 54.7 s); steady ingestion was 156.3 versus 33.3 s; answering was 295.9 versus 308.1 s. The total quoted advantage came from ingestion, despite somewhat slower answering. Repeated report action counts and answer token counts matched the original screen exactly; this is useful reproducibility evidence, not a new independent task distribution.

The dispatch archive's final 24/24 answers do not erase its wrong extra counter in seven accepted checkpoints. Keep that pair outside an exact-quality speed claim. The eight-counter archive missed one historical answer. Both remain in the cost table.

Across sparse rows, answer calls consumed 249–493 KB of cumulatively serialized prompts per trial and 28,885–34,848 completion tokens; 97.3–97.7% of those completion tokens were marked reasoning. Wall minus all logged call times was only 0.72–0.89 seconds per trial. That small residual includes local work and persistence, but HTTP/network time is inside call times and was not isolated. The credible lever is fewer model reasoning/selection turns and less repeated prefill, not faster dictionary or SQLite lookups. Batching can also increase prompt length, repeat work or lose adaptive evidence selection, so no speed ratio can be inferred from these counts.

## Full-source control: actual byte feasibility

Summed verbatim UTF-8 batch text below. The envelope calculation uses the existing source-only answer instruction/system wrapper, conventions, all original questions and exact batches as ordinary fetch response objects, empty saved answers/state/memory, normal remaining-call fields, and the engine's two-stage JSON serialization. The last column reserves a 6,553-byte ASCII memory string. This is a CPU feasibility calculation, not an executed model prompt, tokenizer fit certificate, or guarantee for arbitrary saved state/escaping. An implementation must recheck the final exact serialized prompt and actual tokenizer with its real state and metadata.

| Inputs | Batches | Original source bytes | Full answer envelope bytes | With reserved ASCII memory |
|---|---:|---:|---:|---:|
| Semantic 12 documents | 4 | 494–958 | 3,968–4,432 | 10,521–10,985 |
| Temporal t01–t04 | 12 | 5,882–5,981 | 14,002–14,075 | 20,555–20,628 |
| Sparse8 report83 | 17 | 38,663 | 45,574 | 52,127 |
| Sparse128 report83 | 24 | 57,772 | 65,353 | 71,906 |
| Sparse128 dispatch97 | 24 | 59,560 | 67,141 | 73,694 |

The current limit is **32,768 serialized UTF-8 prompt bytes**, not 32,768 tokenizer tokens. Short temporal tasks leave ample byte space for their eight-counter state; exact new wrappers still need validation. Sparse raw source alone already fails the limit. Larger narrative streams cannot be treated as full-source controls by quietly widening the context or stripping filler/irrelevant prose.

A direct one-shot short-document reader is the simplest separate baseline: give the complete original document, conventions and questions, with the same model, answer thinking/output cap and cold policy, ask for all answers, and charge the whole request's cost. It has no ingestion checkpoints or accepted intermediate state: compare final task accuracy and total work, and mark those state metrics not applicable. Do not present it as the same bookkeeping method with only a faster fetch API.

For the narrower question “how much does navigation cost after bookkeeping?”, instead keep fresh ingestion unchanged and preload all original batches only at answer time. Use identical preload rules for archive and quoted, preserve their actual state/memory and the 32 KB cap, and account for each preloaded batch against the same distinct retrieval budget. This measures forced evidence availability, not model-selected bulk fetch. It is especially useful if short-task source-only retrieval looks expensive; it cannot validate long-context claims. Do not run both baseline variants merely to enlarge a matrix: select the estimand before launch.

## Minimal prospective bulk-fetch contract

Proposed new action: `{"action":"fetch_many","batch_ids":[2,3,4,5]}`. Fixed maximum four batch IDs, positive strict integers, unique, in increasing source order. The legacy one-batch fetch remains available and is equivalent to a singleton. No range expansion, search batching, arbitrary programs or multi-action dispatch. No source rewrite, synthesized history, question-aware compression or oracle material.

1. Resolve each member against the immutable original delivery store. Return individual ID, complete original text, source hash and canonical receipt in source order. Verify source identity independently; never trust text supplied in the request, an edited memory, or the answer reference. State snapshots continue to preserve wrong/missing/extra accepted values.
2. Charge one successful distinct retrieval per newly fetched batch, sharing `fetch:<id>` cache identity between singleton and bulk requests. Re-fetching a cached batch costs no extra distinct retrieval, but every model request consumes an answer-call slot. A batch previously present merely as a search hit still costs a fetch unit. A four-new-batch request costs four of the same 24 units, not one. Keep the 32 answer-call cap, 6,553-byte memory cap and generation caps unchanged.
3. Validate all IDs, membership, budget and serialized response/prompt fit before admitting any retrieval in the group. Model mistakes yield one deterministic recoverable refusal, no partial cache/budget mutation, and no hidden retries. Retain existing partial-answer-save behavior consistently with singleton errors; document that retrieval atomicity does not roll back already submitted partial answers. A missing known batch, hash failure, database fault or persistence failure is infrastructure failure and stops the campaign under the existing policy.
4. All returned members must coexist intact in the immediately following prompt. Evict older evidence with the same deterministic policy in both controls; then apply the same permitted memory clearing. If the requested group still does not fit, refuse it with a bounded “request fewer batches” response. Never silently truncate text, show only the last member, charge unseen members, grant a bigger context, or make additional hidden model calls. Record evictions and exact final prompt bytes. Later evidence retention uses identical per-batch rules in singleton and bulk arms.
5. Log requested IDs, individual accepted/cached/refused outcomes, before/after budgets, individual text/receipt hashes, response hash, prompt hash and byte count. Preserve failed attempts and all time/tokens. Audit distinct-batch charges independently from action count; report both. Byte and tokenizer reference checks must be free of oracle data in executed prompts.
6. Apply the same source-fetch capability to both bookkeeping arms and both source/history access modes. Source-only must still deny `state_at`; history still returns only actual accepted snapshots and still needs source text for historical ownership. Do not add bulk `state_at` in the same treatment. The resulting experiment measures bulk-source API plus its instruction wording, not a pure change in transport. If comparing history against source-only, both must receive the same bulk-source option and pay identical snapshot persistence costs.

CPU tests could establish singleton equivalence, exact multi-source provenance/order, duplicate/Boolean/out-of-range rejection, mixed cached/new accounting, insufficient-budget atomicity, boundary byte-fit and escaping, oversized-member refusal without truncation, denied source-only history access, tamper/storage failure classification, failure evidence preservation and absence of oracle fields in model payloads. These tests cannot establish whether a model correctly chooses batches, reconstructs past state or maintains accuracy with fewer turns.

## Bounded follow-up, after the frozen study decision

Finish all eight current history cells unchanged and apply its already registered continuation rule. If it admits t03/t04, preserve that separately frozen extension with the original interface and fixed order; batching does not replace or contaminate it. If it fails, diagnose its ingestion/ownership/retrieval category before preparing another lever. Nothing in this note admits a launch, holdout or speed claim.

For a subsequent bulk-source feasibility study, a bounded first block can hold source-only access fixed and compare archive/quoted × singleton/bulk on two documents chosen in advance, with eight fresh trials and reversed condition order on the second document. This avoids immediately doubling to a sixteen-cell method × history × batching study. Keep history access disabled in both treatments, while retaining identical snapshot persistence in their shared engine; existing history results remain a separate policy comparison. Do not choose the two documents because they looked favorable under current outputs. For a short-document question, the simpler full-source baseline should usually precede that eight-cell bulk matrix. For genuinely over-window inputs, bulk fetch is the applicable lever and a full-source baseline is explicitly out of scope.

Preregister retained failures, exact-state/event/answer quality gates, cold evidence, cost decomposition and a modest continuation criterion before observing new outputs. A candidate must preserve quality before a speed ratio is meaningful. A timing signal on one server remains diagnostic; the lab's two-fresh-server rule and realistic-workload limits still apply. The present authored/templated workloads cannot justify a broad practical speed headline.

## Evidence paths and reproduction boundaries

Read-only inputs were the three completed diagnostic roots below, each row's native `result.json`, `calls.jsonl`, `retrieval.jsonl` when present, plus outer sparse phase-cost receipts; frozen `semantic_v1/{live.py,answers.py,tasks.py}`, `history_v1/{live.py,answers.py}`, the frozen next-study decision/active study plan, and source documents/compiled task inputs. No current history output was read. The table definitions above allow independent recomputation without executing a model or modifying any frozen file.

Summary file identities at inspection:

- `/mnt/fast-ai/bench-results/context-semantic-v1-20261007/diagnostic/summary.json` — SHA256 `09dfa342622b8c9f8dcfafc2b57ab7ecffebc13fc7ac4e394a06d12cd662f218`
- `/mnt/fast-ai/bench-results/context-sparse-v1-20261007/diagnostic/summary.json` — SHA256 `44955b044003aa889f1455d30ab4c87cf8cd71a1e26c747dc762b8ec61b0306f`
- `/mnt/fast-ai/bench-results/context-sparse-replication-v1-20261007/diagnostic/summary.json` — SHA256 `9abcb4413045f39bc7e0a59238bcd89dde30fc88d0c0face8baa5706541279b0`

Relevant source inputs are under `experiments/qwen38-27b-b70/data/{2026-10-07-context-semantic-development,2026-10-07-temporal-development,2026-10-07-sparse-state-development,2026-10-07-sparse-state-replication}`. The temporal source remains SHA256 `45ae96b4c80dca9a14defddf1bf33ae895e47fed9848101dbdc9ae2cb2be666f`. The frozen continuation authority is `notes/2026-10-07-context-next-study-decision.md`, interpreted together with `notes/2026-10-07-history-state-study-plan.md`.
