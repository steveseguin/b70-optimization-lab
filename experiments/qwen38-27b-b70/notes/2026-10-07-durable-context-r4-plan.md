# Durable context revision 4: fresh confirmation and uncached timing

The owner asked to continue. Revision 3 completed its four structured-method
trials at 24/24 each. Summary scored 22/24 in each style, retaining two incorrect
current totals. **Revision 3 failed its original all-methods gate**; none of its
results is reclassified here, and no held-out seed was used.

A separate timing audit found prefix-cache reuse in quoted-event answer calls.
The existing timing gate did not inspect cache usage. Revisions 2 and 3 made no
qualifying speed claim because their quality gates failed; their recorded elapsed
comparisons also cannot support a speed claim because of cache contamination.
Preserve those sources and results unchanged.

## Prospective claim and gates

This revision narrows the primary question to **quoted events versus the
model-maintained archive table**. Summary remains a secondary diagnostic with
all its results and costs reported. Its accuracy need not be perfect, but every
planned trial, including summary, must complete cleanly with a valid submission.
A missing, resumed, malformed, failed or partial trial blocks qualification.
Every primary-pair answer must be correct. Keep the separate all-methods accuracy
verdict visible. This change is motivated by inspected development results and
is not retroactive evidence that either earlier revision passed.

Confirm on new development seeds **17 and 29**, both report and dispatch styles,
48 batches and 320 filler words: 12 trials, including eight primary trials that
must each score 24/24. Do not select only successful cases. Calibration stays at
seed 7 with the same two fixed 16-batch extraction diagnostics. The two authored
styles share a generator and underlying per-seed events; they are not independent
natural-document samples.

Only after the declared fresh-development gate passes may the still-unused
held-out seeds 401, 502 and 603 run in both styles: all 18 trials. All primary
held-out answers must be correct, with the same completion requirements for the
full matrix. Tasks, source bytes, generation policy and server identity are frozen
before requests. No oracle is supplied to real model prompts.

## Cold request policy and timing

Derive a cold profile from the recorded qualified Plan-E launch without changing
that historical file: prefix caching off; remove the prefix-cache-retention
argument; retain pinned image, arithmetic precision, KV precision, MTP, overlays,
memory and context settings. Omit the owner's warmup request. Verify actual
emitted arguments contain `--no-enable-prefix-caching`, have no enabling override
or aligned recurrent-cache mode, before sending the strict or experiment requests.
Re-run the standing 12/12 reference qualification because the cache mode changed.

Every logged request must report an integer cached-token count of zero for its
trial to support timing. Missing, malformed, negative, boolean, excessive or
positive counts fail timing eligibility. Independently recompute this from raw
call logs; do not trust aggregate result fields. Quality and timing verdicts are
separate. Nevertheless admission to fresh held-out testing requires verified
zero cache usage in every development trial, including summary; a violated or
unverifiable cold-request policy blocks that admission. All reasoning and output tokens remain part of measured cost.

One cold server can provide a descriptive paired ratio only. The single-server
10% improvement signal is **not** a speed verdict or headline. Require a second
freshly qualified cold server and complete paired replication before considering
such a claim. If the first cold comparison is slower, report that outcome and
choose a worthwhile next lever; do not keep retrying for a lucky server.

## Unchanged model-facing experiment

Use revision 3's final-answer policy: thinking on, medium effort, 8192 combined
reasoning/answer output tokens. Ingestion/extraction remain thinking off with
4096 output tokens. Retain the 32,768-byte prompt, 32 answer calls, 24 distinct
retrieval operations, exact batch lookup, saved answers and explicit submission.
Do not change prompts or retrieval semantics in this confirmation revision.

One supervised run, no automatic server retries or resident service, no reset,
power or host-memory-setting changes. Stop the owned server on completion or
failure and preserve all evidence. Stronger future external-validity checks need
independently authored and independently graded documents, shuffled references,
corrections/cancellations and more varied historical questions; this remains a
synthetic pilot until those checks exist.

Sources: `scripts/context/durable_v4/` and `durable_v4_host_runner.py`.
Data: `data/2026-10-07-durable-context-r4/` (calibration, development and holdout).
First output: `/mnt/fast-ai/bench-results/context-durable-r4-20261007`.
Owned unit: `ctx-durable-r4.service`.
