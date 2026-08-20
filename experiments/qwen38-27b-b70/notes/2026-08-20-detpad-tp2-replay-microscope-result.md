# Qwen3.8 sealed TP2 prompt-24 replay microscope result

Date: 2026-08-20

Status: **invalid trace false-null; preserve and do not retry**

M1 did not engage the replay microscope. The trace file was never created, so
the arm contains no stage-level localization evidence. Independently, prompt 6
ended normally at 68 tokens with EOS token `248046`; that made the strict
100-token measurement window incomplete, returned `bench_rc=2`, and caused the
post-run qualifier to fail. The final runner exit was `1`, before the formal
sealed arm checker could run.

The displayed count-24 median, `102.413900 tok/s`, is invalid and must not be
compared, promoted, or submitted.

## Why the trace was empty

The false-null is fully explained by a request-ID namespace mismatch, not the
token-window filter or an API-process environment omission.

- OpenAI chat serving creates the public ID `chatcmpl-<X-Request-Id>` in the
  pinned `vllm/entrypoints/openai/chat_completion/serving.py`.
- `AsyncLLM` then calls `InputProcessor.assign_request_id`. It preserves that
  value as `external_req_id` and changes the engine/worker ID to
  `<external_req_id>-<8 random hex>`.
- The microscope matcher reads worker-side `input_batch.req_ids`, but M1's
  anchored regex accepted only the unsuffixed public ID.

The launched regex therefore could never match. The prompt-token gate of 849
was correct but was never reached after request matching rejected the internal
ID. All eight microscope variables were visible at API startup and the pinned
source was loaded. The run has no microscope worker-init marker or trace, so it
does not independently prove that those variables reached the TP workers; the
namespace mismatch is sufficient to explain the empty trace either way.

The generic contract is corrected for future, separately preregistered work:

```text
^chatcmpl-bench-qwen36-27b-int4-independent-validation-20260815-v1-24-holdout--long-rollover-repository-audit-[0-9a-f]{8}$
```

M1 itself will not be rerun. Its original launcher, run-arm, and checker bytes
remain frozen under `run/*.snapshot`; plan commit `0cfeddb59` also preserves the
launched unsuffixed contract.

## Preserved output evidence

M1 still returned 25 unique cached-zero responses, but prompt 6 did not contain
the required metric window. Its token arrays are report-only recurrence data:

| Comparison | Exact token arrays | Mismatching prompts |
| --- | ---: | --- |
| M1 versus S1 | 23/25 | 6, 11 |
| M1 versus A2 | 22/25 | 6, 11, 24 |
| M1 versus B2 | 22/25 | 6, 11, 24 |
| M1 versus C1 | 22/25 | 6, 11, 24 |

- Prompt 6, `selection--sql-debugging`, produced a 68-token family ending in
  EOS `248046`. Its token-array SHA is `2e872a88...` and output SHA is
  `1bde8184...`.
- Prompt 11, `holdout--factual-protocol`, produced a 512-token family with
  token-array SHA `0454b482...` and output SHA `569801f2...`.
- Prompt 24 exactly matched S1's complete 512-token family, starting
  `71093,13102,198`, with token-array SHA `b1ad815b...` and output SHA
  `471a54e8...`. It differs from B2 at generated token 469 and from the A2/C1
  all-zero family at token 0.

Because the filter never matched, none of those endpoints can be attributed to
microscope execution.

## Raw integrity evidence

The formal arm checker did not run and no `tp2-sealed-gates.json` exists. The
following are independent raw observations, not a claim that the sealed gate
passed:

- checksum manifest `1a4f4a84...` verifies every preserved file;
- model verification passed all 19 direct and ordinary views;
- smoke passed;
- both TP ranks emitted one INT4 determinism-pad marker;
- two b991 outer graphs and four AOT artifacts loaded directly;
- no graph/AOT compile or save marker appeared;
- cache input and output manifests are byte-identical at `f3582440...`, tree
  `723c1599...`, 3,795 entries, 3,246 files, and 395,855,113 bytes;
- the supervised process group shut down empty.

Artifact checksums:

- benchmark JSON: `533e0d2fbcd58c07d61a5f13f105069232f0af415209e0e9556e2e5e240bca2b`;
- checksum manifest: `1a4f4a84eb4dfaf2928242bd66248013a83a96f1e9e2700e7bb4e45cbf1468cb`;
- cache input/output manifest:
  `f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff`.

Artifact root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-marginfree-mtp5-25-replay-microscope-m1-20260820`

## Decision

Preserve M1 exactly. Do not regenerate its checksum set, fabricate a trace or
sealed-gate result, qualify the benchmark in place, or rerun the same
microscope. It establishes neither localization nor speed. GPU diagnostics
stop here until a distinct source-backed hypothesis and new preregistration
justify another arm.

Structured evidence:
[`../data/2026-08-20-int4-detpad-tp2-replay-microscope-result.json`](../data/2026-08-20-int4-detpad-tp2-replay-microscope-result.json)

Preregistration:
[`2026-08-20-detpad-tp2-replay-microscope-prereg.md`](2026-08-20-detpad-tp2-replay-microscope-prereg.md)
