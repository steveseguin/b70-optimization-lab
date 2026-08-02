# Laguna long-context mixed-depth feasibility diagnostic

Date registered: 2026-08-02 America/Toronto

Status at registration: diagnostic tooling is committed; no new service has
started and no mixed-depth source implementation exists.

## Question

The 32K q12 candidate sustains about 39--40 tok/s with less than one percent
draft-token acceptance. The q8 screen was slower because it reduced both the
DFlash proposal depth and the target verifier width. This diagnostic asks a
narrower question: do any 32,640-token rows actually accept a draft token past
position 6?

If not, a future source treatment may be able to compute only seven DFlash
proposal rows while preserving the proven twelve-row target verifier. The
remaining target candidates would be deterministic invalid/padding proposals;
the unchanged target would still verify every emitted token. This is only a
feasibility screen. It does not authorize padding semantics, a source change,
or a throughput claim.

## Frozen identity

- main tooling commit: `8777290ab`;
- vLLM: exact-prefill source `4ddb915284d4442885f72bed48311fd04640977c`;
- XPU kernels: `99886d783372e621941228250091dc8ebdc1595d`;
- q12 target / DFlash depth 11, exact max M12, TP4/EP4, BF16 KV;
- exact-prefill selector on, segmented DFlash plus inline attention on;
- `max_model_len=32768`, `max_num_batched_tokens=8192`, GPU utilization 0.80;
- temporary 24 GiB total swap, 8 GiB available-RAM guard, and the normal
  4 GiB free-swap guard; and
- one 1,024-token warm-up followed by all early/middle/late 32,640-token rows
  and their automatic 256-token sentinels.

Use the previous exact-prefill run as the repeatability oracle:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/`
`laguna-exact-prefill-chunks-32k-warm-gpu080-20260802T191200Z/bench.json`.
Every selected output and prompt hash must match it exactly. This does not
upgrade the known q1-long-output caveat.

The updated benchmark must record per-request deltas for
`vllm:spec_decode_num_accepted_tokens_per_pos_total`, require their sum to
equal the ordinary accepted-token counter, and report the highest accepted
draft position. The per-position counter schema must remain fixed during each
request.

## Gate and stopping rule

Mixed-depth source work is authorized only if all three 32,640-token rows:

- pass intrinsic, retrieval, cache-zero, repeat-oracle, topology, cleanup, and
  memory gates;
- have a per-position sum exactly equal to their accepted-token total; and
- record zero accepted tokens at positions 7 through 10.

The sentinels are expected to accept deeper tokens and therefore prove that a
future treatment must be explicitly long-context-only. Any long-row token
beyond position 6 closes this exact depth-7 hypothesis before implementation.
Any operational failure is preserved with no retry or guard change.
