# Qwen3.8 Flash-Next FP8 A26 async-UVA endpoint result

Date: 2026-08-30
Status: rejected at exact-4K repeat and authority gate

## Outcome

A26 was the first and only full Flash-Next load in boot
`d93d5dff-2637-436a-9bc8-8c94020294d0`. The checkpoint stayed on local NVMe:
all 131 shards loaded in at most 80.16 seconds, each rank reported 31.57 GiB of
device memory and 11.92 GiB of host PLE, and the endpoint exposed a 4,747-token
cache for the frozen 4,352-token ceiling.

The component-exact async-UVA candidate did not pass the endpoint contract.
Recovery passed; quality retained the accepted 6/7 boundary with only the
known code case missing; the short repeat stayed at one hash for 16/16; and the
exact-4K needle and both cache-zero transport gates passed. The three short
rows retained the protected output hash at `5.452989 / 5.364522 / 5.395973`
tok/s, median `5.395973 tok/s`. That is 2.17% below the protected
`5.515783 tok/s` median, so the candidate receives no short-speed credit.

The two exact-4K rows measured `5.276427 / 5.192318 tok/s`, with TTFT
`114.453 / 108.876` seconds. They produced different hashes,
`47fbaefe...193e` and `5a6c744a...a654`; neither equals the retained authority
`1d833e5f...d5cc`. The final assertion failed closed. The apparent TTFT range
overlaps the A24/A25 cross-boot variation, so this unmatched negative does not
support a prefill-speed claim either.

This is an important separation of evidence: the side-stream lookup is exact
for fixed inputs and remains preserved as component research, but scheduling
it early does not make the complete endpoint reliable and does not improve
target decode. Do not promote `VLLM_XPU_PLE_UVA_PREFETCH=1`, and do not repeat
this endpoint arm. The existing layer-1 GatedDeltaNet localization remains the
reliability lead; the already exact MoE and collective component candidates
have better odds for the next target-speed arm.

## Lifecycle

The client wrote the expected failure sentinel and the supervisor terminated
the owned process group. Port 19698 disappeared, no model process remained,
all four cards returned to about 43 MiB, and host memory recovered above
126 GiB with more than 8.3 GiB swap free. The kernel-window gate passed. Four
Samsung-NVMe receive-error reports appeared, one also carrying a nonfatal
status bit, but there was no NVMe reset, GPU loss, OOM, or host freeze.

Protected `5.515783 tok/s` target-only and approximately `20.727 tok/s` MTP4
results are unchanged. Structured result:
[`20260830-tp4-mtp0-a26-async-uva-endpoint-negative.json`](../data/20260830-tp4-mtp0-a26-async-uva-endpoint-negative.json).
