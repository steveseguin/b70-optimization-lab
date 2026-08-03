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

## Result

Status: closed as an operational failure; the mixed-depth hypothesis remains
unmeasured and source implementation is not authorized.

The frozen run artifact is
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/`
`laguna-long-mixed-depth-feasibility-q12-20260802T211100Z`. Runtime verification
passed and all four workers reached distributed initialization, but the server
log stopped growing after the final topology warning at 17:12:54 local time.
Unlike prior matching starts, it never printed `Starting to load model` or a
checkpoint progress line. No health endpoint, benchmark process, benchmark
row, graph capture, or performance measurement was reached.

At 17:15:30, after the service had already made no progress for more than two
minutes, an observer `xpu-smi dump` was started to inspect the devices. That
observer also hung. Beginning at approximately 17:15:33, the kernel reported
repeated GuC execution-queue timeouts and resets for `0000:47:00.0`, including
`Kernel-submitted job timed out` and timed-out jobs reported as belonging to
`no process [-1]`. The observer may have participated in or exposed the bad
device state, so these messages must not be attributed solely to vLLM. They do
make the service run invalid. At the time evidence was collected, the boot log
contained 17 distinct affected sequence numbers from 262239 through 262257.

The launcher was interrupted through its normal cleanup path rather than
waiting for the full startup deadline. Cleanup recorded `original_status=130`
and `stop_status=0`; no vLLM worker or port-18080 listener remained. The memory
guard never fired: its minimum `MemAvailable` was 121,612,888 KiB and minimum
`SwapFree` was 25,027,888 KiB across 467 samples. The temporary 16 GiB swap file
was disabled and deleted after cleanup, restoring the host to its normal 8 GiB
swap configuration.

Per the frozen stopping rule there is no retry, guard relaxation, or source
implementation from this run. A later fresh-device campaign must repeat the
diagnostic before the position-7-through-10 acceptance gate can be evaluated.
Structured status and artifact hashes are in
`data/laguna-s-2.1-xpu-b70/long-context-mixed-depth-feasibility-20260802.json`.

## Offline successor tooling (2026-08-03)

The next run's decision is now automated by
`tools/analyze_laguna_long_mixed_depth.py`. It preserves this stopping rule,
requires the exact warmup/three-long/three-sentinel sequence, fails closed on
all intrinsic/oracle/cache/metric drift, requires every long row to have zero
acceptance past position 6, and requires every sentinel to prove deeper short
acceptance. Six CPU-only tests pass. This does not alter the failed result or
authorize a retry; see
[`2026-08-03-mixed-depth-analyzer-offline.md`](2026-08-03-mixed-depth-analyzer-offline.md).
