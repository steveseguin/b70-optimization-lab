# Laguna 32K static q8/depth-7 screening preregistration

Date registered: 2026-08-02 America/Toronto

Status at registration: no q8/depth-7 service has been started under the
32K lane. This note freezes the candidate, screening order, gates, and claim
boundary before the runner is changed or any generation begins.

## Question and claim boundary

At a 32,640-token prompt the current q12/depth-11 candidate accepts only
about 0.56% of draft tokens, but still decodes at about 39.75 tok/s across
the three long rows because an exact 12-row verifier cycle is much cheaper
per emitted token than target-only q1. This screen asks whether the previously
validated exact q8/depth-7 target graph reduces that long-context verifier
cycle enough to improve decode throughput.

This is an experimental long-context screening lane. It cannot replace or
modify the protected short-context q12 record, and it cannot support a
LocalMaxxing submission. A passing screen only authorizes a separately
preserved short exactness check and a complete three-position 32K campaign.

## Frozen comparison

Reference evidence:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-exact-prefill-chunks-32k-warm-gpu080-20260802T191200Z
```

The matching `laguna-lc-32640-middle` q12 row measured:

- conventional first-100 decode: `40.38107993869617 tok/s`;
- DFlash acceptance: `0.006436041834271922`;
- retrieval: pass; and
- completion length: 128 tokens.

The q8 screen must run the same fixed suite and select, in order:

1. `laguna-lc-01024-early` as an unscored service warm-up; and
2. `laguna-lc-32640-middle` plus its automatic post-long sentinel.

There is no oracle for this screen. Retrieval, response-shape, prompt-token,
cache-zero, and sentinel checks remain mandatory.

## Frozen candidate identity

- main tooling starts from commit
  `7239e4bf78613b873eb15fd7edea8a8b2e579090`;
- vLLM: `1a7f61feffbc61b21b73f812d231c7426386ccdc`;
- XPU kernels: `99886d783372e621941228250091dc8ebdc1595d`;
- target and DFlash revisions remain the frozen Laguna revisions;
- TP4/EP4/PP1/DP1, BF16 target and KV cache, one active sequence;
- maximum model length 32,768 and chunked prefill size 8,192;
- DFlash q8/depth-7, greedy draft sampling, standard rejection sampling;
- target Breakable graph capture size 8 with the exact M8 verifier;
- prebuilt exact attention metadata, M8 shared-elementwise, fused
  W1-route-W2, route interleave, QKNorm/RoPE, and W1 N64 remain enabled;
- q12-only BF16 router, DFlash context workspace, FP8 drafter, segmented
  drafter graph, inline drafter attention graphs, and M12 shared-elementwise
  are explicitly disabled; and
- no exact-prefill chunk selector, prefix cache, async scheduler, local
  argmax, retries, request concurrency, or retained service state.

The expected target graph topology is `146/145` on all four ranks. No drafter
graph topology is expected because the q12-only segmented drafter graph is
disabled.

## Frozen screen gates

The candidate passes screening only if all of the following hold:

- `laguna-lc-32640-middle` retrieval and every intrinsic row check pass;
- the post-long sentinel passes and no stale cache is reported;
- conventional first-100 decode is at least
  `41.59251233685705 tok/s`, 3% above the matching q12 row;
- all four ranks log the expected `146/145` target topology;
- there is no drafter graph capture, runtime/device error, memory-guard stop,
  retry, or surviving process; and
- the complete benchmark and service identity is preserved on NVMe.

A result below the throughput threshold, any correctness failure, or any
runtime failure closes this static q8 candidate as a loss. A borderline result
may be repeated only as an explicitly documented noise-resolution run; it may
not silently replace the first result.

## If the screen passes

Run, under fresh services:

1. the canonical short suite against the q1 oracle to prove bitwise exactness
   and quantify the expected short-context regression; and
2. the complete warmed 32K early/middle/late suite with sentinels, comparing
   all three rows to the preserved q12 evidence.

Only after those gates pass should adaptive context-aware depth selection be
considered. Static q8 remains an experiment and the production q12 record lane
stays unchanged.

## Pre-launch audit correction

Before any q8 service start, an independent source audit found that the first
tooling commit inherited `VLLM_XPU_LAGUNA_DECODE_GRF128=1` and
`VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=1` from q12. Both selectors are
width-12-only. GRF128 is dormant at q8, while transposed scales eagerly create
persistent scale-table clones in every target MoE layer and only consume them
when `num_rows == 12`. At 32K this is pure memory cost.

The frozen q8 identity is therefore corrected to require both selectors at
literal zero. The q12 default continues to require both at one. This correction
narrows the q8 candidate to its actually exercised code and was committed and
contract-tested before the first service launch; it does not replace any run.

## First screen result: terminal guard stop, unmeasured

The frozen screen started at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-long-depth7-screen-gpu080-20260802T201509Z
```

It completed runtime verification and all four ranks captured the exact q8
target topology `146/145`. Before any completed benchmark row or graph replay,
the memory guard stopped the service at `12,504,872 KiB` available, only
`78,040 KiB` below the frozen `12,582,912 KiB` floor. Swap free was still
`24,940,828 KiB`. Cleanup succeeded, no worker survived, and port 18080 was
free. The artifact is sealed with a zero-row `RUNNING` benchmark file and exit
status 143; it contains no throughput, retrieval, or acceptance result.

The successful q12 32K comparison had explicitly used an 8 GiB available-RAM
floor. This q8 launch accidentally inherited the runner's 12 GiB default, so
the guard identities did not match. The preregistered failure policy is still
honored: the static q8 plus 8,192-token prefill candidate is closed as an
operational failure and will not be rerun under a relaxed guard.

The durable structured result is
`data/laguna-s-2.1-xpu-b70/long-context-depth7-screen-20260802.json`.
