# Canonical Q8 Phase-1 first-hit pass

Date: 2026-08-09 local / 2026-08-10 UTC

## Classification

The fresh four-card Phase-1 cohort passed. It establishes selector-matched c1
oracles for the no-sleep canonical-Q8 runtime and proves the expected
selector-off/selector-on first-hit behavior without relying on teardown
counter summaries. This is diagnostic correctness and route evidence only;
it is not a c2 result or a performance result.

Sealed packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c1-oracle-four-gpu-20260810T013725.235133447Z`

- exhaustive `wave-artifacts.sha256` SHA-256:
  `2871f4947a06a99f28ea813dbb1b092f638336ef46be6631d79f7528fe98259c`;
- phase-summary SHA-256:
  `5550e5a60f577d6642d750b1f7035759a286ffcb383e35497e0c546f2d46741b`;
- detached completion-marker SHA-256:
  `5335f67a5b5a177ae6bada2cabb45f6c1fc45cc62f285072e2ceefa572d6ce01`;
- classification: `EVIDENCE_VALID`, `diagnostic-only`,
  `performance_promotable=false`;
- all 321 outer-manifest entries and all four 37-entry lane manifests
  independently verified.

The packet pins the candidate server SHA-256
`1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`,
runtime-manifest SHA-256
`1b6c305b7e3fad027e7397168bda23526b72b8a4b59e8c6b2b3788fc7347b4d9`,
canonical SYCL DSO SHA-256
`f0a9e736dde321f72fceb14db6fb1410a9ad090380a3cf8ed7c591e949c94305`,
model SHA-256
`f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce`,
runner SHA-256
`a704178e80670ac5393d4e110d95059497354918768b3074f1af62b32a4fe51a`,
and analyzer SHA-256
`83e956070365a57d2e0d7910d72f9fa723538a661d91d3bb7ad51b45a3fc38a2`.

## Correctness and route evidence

All four fresh c65536/np2/non-unified-F16-KV servers captured A in slot 0 and
B in slot 1 sequentially, with 512 forced tokens per case. GPUs 0 and 1 ran
the selector off; GPUs 2 and 3 ran it on.

Every lane matched the official sealed c1 packet and fixed schema adapter for
the full token arrays, content hashes, prompt hashes, rendered-prompt hashes,
semantic retrieval checks, and external canaries. The A row was identical on
all four cards:

- token-array SHA-256:
  `c9754bee39df823b7450c1793a0824f6f3e115f6831cf4281dc2a5a323c6cf91`;
- content SHA-256:
  `0d9d47550a141926d07655a6bfc32600e09604c5fc004e4daa1e7001078800d1`.

The B row was also identical on all four cards:

- token-array SHA-256:
  `415b37ddb9199a6ec992660ff0aab92842af1c21f50ff454ae86029ba59457a7`;
- content SHA-256:
  `aaad8a7d750cf67a188520e3c96ffb30d77a1f58f6df52b45022e2863dc5fee5`.

The selector-matched Phase-2 handoff oracles are:

- selector off: `selector0-oracle.json`, SHA-256
  `62a3e2991f697db2e420a49ddb048539cf94f1fd436f93b3f48b08eb8b38d573`;
- selector on: `selector1-oracle.json`, SHA-256
  `bb179eac0ffa11bffc2d56f77b309ccdf62fcbce193f56a1cb9efbc944e6a2d4`.

The two selector-off lanes contain zero canonical first-hit, summary, or
violation markers. Each selector-on lane contains exactly one flat first-hit
before release, retained unchanged through the frozen postcapture prefix:

`layout=flat path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 src0=blk.0.attn_qkv.weight src0_ne=[5120,10240,1,1] src1_ne=[5120,2,1,1] dst_ne=[10240,2,1,1]`

Neither selector-on lane contains a recurrent first-hit or violation marker.
No summary was retained, which is permitted by the first-hit contract; no
process-total count, request-time dispatch, c2 correctness, or rate claim is
made.

## Lifecycle and operational caveat

All four servers terminated gracefully. There was no forced kill, cleanup
survivor, residual lane process, or listener. The retained final XPU samples
show 43 MiB used on every card, and the pre/post device and server fault scans
are empty.

The retained kernel window includes one hardware-corrected PCIe RxErr at
`0000:01:00.0`, vendor/device `144d:a80a`, class `010802` (the NVMe endpoint),
not one of the B70 display devices. It required no action, produced no Xe or
model-process fault, and does not invalidate the GPU evidence. It remains an
operational host event worth preserving separately from the model result.

## Next gate

Phase 2 must consume these exact fresh selector-matched oracles and preserve
the same no-sleep server identity. The preregistered two-wave crossover keeps
each physical card on one heterogeneous scenario and flips the selector on
that same card between waves:

- forward A0/B1 on GPUs 0 and 1;
- reverse B0/A1 on GPUs 2 and 3;
- wave 1 uses off/on/off/on; wave 2 uses on/off/on/off.

Each fresh lane must prove exact full-512 output against its matched c1 oracle,
true M2 occupancy and synchronization, cache-zero/input integrity, PID/runtime
continuity, clean teardown, and the selector route contract. Selector-on must
retain flat then recurrent first-hits in the declared boundary order;
selector-off must retain zero canonical route markers. B71 and A96 are
baseline landmarks only, later forced-tail hashes are not endpoints, and no
majority vote or aggregate performance rate is permitted.
