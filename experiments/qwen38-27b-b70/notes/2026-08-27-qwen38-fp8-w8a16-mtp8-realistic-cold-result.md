# Qwen3.8 FP8 dynamic-MTP8 cold realistic result

> **AUDIT CORRECTION, 2026-08-27 — diagnostic only; not a record, package
> headline, or valid submission source.** Both attempts used a 128-token output
> cap. The promotion policy required the complete varied-prompt suite under a
> 512-token natural-completion cap, plus independent quality/determinism gates.
> The old harness incorrectly emitted `realistic_final_gate.passed=true` when a
> run merely covered the first-100-token metric window. The measured
> `58.391033 tok/s` center remains useful screening evidence for this exact
> 128-token-cap service, but it is not promotion-grade. The selected
> high-acceptance `146.814418 tok/s` fixture is also diagnostic only.

The first chronological run was prematurely submitted and is approved on LocalMaxxing as
[`cmtb5n45n0021qq01n13vly2h`](https://www.localmaxxing.com/runs/cmtb5n45n0021qq01n13vly2h).
Withdrawal is recommended. That external row reports R1 directly; it does not
substitute a compliant two-server package result.

| Fresh server | conventional 99-interval median | p10 | full after-TTFT median | wall median | TTFT median | first request TTFT |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| R1 | 58.537756 | 48.117648 | 58.549396 | 55.436231 | 108.094 ms | 828.819 ms |
| R2 | 58.244309 | 47.896683 | 58.347267 | 55.270330 | 107.450 ms | 742.776 ms |
| diagnostic two-server center | **58.391033** | **48.007166** | **58.448332** | **55.353281** | **107.772 ms** | — |

The run-median range is 0.503%. Each attempt used a new container and empty
compile cache. All 24 unique cold requests returned 128/128 tokens, all 3,072
output tokens were captured, every request reported `cached_tokens=0`, and
both passed the old, insufficient screening gate. They fail the promotion gate
because the output cap was 128 rather than 512. Timing uses streamed token IDs and the 99
intervals between generated events 1 and 100 after TTFT. Prefix caching,
history acceleration, response reuse, context checkpoints, and `ignore_eos`
were all disabled.

Container start to HTTP readiness was 165.327/164.822 seconds. Engine
initialization consumed 90.29/90.31 seconds, including 71.85/72.26 seconds of
empty-cache compilation. On the first inference of each server, three EAGLE
preparation kernels still JIT-compiled, causing the 829/743 ms first-request
TTFT. This cold-start cost is real and remains in the evidence.

The speed gap is primarily workload-dependent speculative acceptance. The
server reported MTP8 draft acceptance around 26-34% over the varied prose
suite, versus the high-acceptance behavior implicit in the earlier fixed
40-token fixture. The earlier 146.814418 tok/s observation is retained only as
a diagnostic of that selected fixture and is excluded from package headlines
and public graphs. The separately measured c64 aggregate remains short-context
capacity evidence under its own workload and is not single-user speed.

The model, image, patches, TP2 topology, FP16 KV, block-W8A16 dispatch, and
dynamic MTP8-at-c1/MTP1-at-load policy are unchanged from the selected package.
MTP accepted tokens are verified by the declared official FP8 target. Full
structured evidence and logs are in
[`../data/qwen38-fp8-w8a16-mtp8-realistic-cold-20260827/`](../data/qwen38-fp8-w8a16-mtp8-realistic-cold-20260827/),
with the compact summary in
[`../data/2026-08-27-qwen38-fp8-w8a16-mtp8-realistic-cold-summary.json`](../data/2026-08-27-qwen38-fp8-w8a16-mtp8-realistic-cold-summary.json).
