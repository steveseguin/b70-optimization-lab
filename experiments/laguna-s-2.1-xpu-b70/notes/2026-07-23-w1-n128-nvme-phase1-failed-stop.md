# Laguna routed-W1 N128 local-NVMe phase-one failed stop

Date: 2026-07-23 America/Toronto

## Result

The recovered, frozen routed-W1 endpoint campaign stopped after A1/B1 exactly
as preregistered. Both legs were honest and bitwise exact, and N128 removed
real target-cycle work, but it lost the official endpoint comparison:

| Metric | A1 N64 control | B1 N128 candidate | B1 - A1 |
| --- | ---: | ---: | ---: |
| Headline median tok/s | **34.969418822** | 34.029104704 | -0.940314118 (-2.6890%) |
| Mean tok/s | 38.223511425 | 39.176425110 | +0.952913685 |
| p10 tok/s | 24.221875960 | 26.815770749 | +2.593894789 |
| Target-cycle time | 94.093806528 ms | **90.341118198 ms** | -3.752688330 ms (-3.9882%) |
| Acceptance | 4,641/12,047 | 4,642/12,040 | +0.030703 percentage point |

B1 won only **3/13** paired prompt rows. The paired median was
`-0.940314118 tok/s` (`-3.057791%`). It therefore failed the three frozen
performance gates requiring a faster headline, at least 9/13 row wins, and a
positive paired median. It passed the cycle-saving and bounded work-drift
gates.

The classification is `phase1_failed_stop`. B2 and A2 were not run, no rescue
or fifth run is permitted, and no LocalMaxxing payload was staged or
submitted. The approved record remains `33.89498511171744 tok/s`,
`cmrx6p5dv001bo4017hb7sixz`.

## Quality and honesty

Both fresh services passed every frozen source, model, runtime, freshness,
accounting, exactness, and cleanup check:

- canonical q=1 greedy teacher exactness: **13/13 + 13/13** complete token
  arrays;
- cache-zero: **13/13 + 13/13**;
- long-then-next exactness: **2/2 + 2/2**;
- rollover exactness: **1/1 + 1/1**;
- one request for each of 13 unique cold prompts, with no generation warmup,
  cache/history/ngram/response reuse, or concurrency;
- distinct service processes and a 172-second four-device idle gap;
- identical main-repository commit during both legs; and
- zero-status bounded shutdown and post-stop device/process proof for both
  legs.

The only treatment difference was literal
`VLLM_XPU_LAGUNA_M8_W1_N_TILE=64` versus `128`. The complete approved
shared-elementwise + QKNorm/RoPE + route-interleaved DFlash stack remained
fixed.

## What the result means

N128 is a real isolated kernel optimization, not an endpoint win. The prior
four-card component gate measured an 8.7271% mean isolated W1 improvement, and
this endpoint phase still saved 3.7527 ms per normalized target cycle.
Nevertheless, ten prompt rows slowed and both robust endpoint summaries moved
against the candidate. The larger tile is therefore closed as a promotion
candidate for this exact stack.

The mean and p10 are reported as secondary observations only. A large cold A1
first-row slowdown raised B1's mean comparison, but the frozen primary median,
row-win count, and paired median all reject N128. No post-hoc metric replaces
those gates.

## Source and local-storage identity

- main repository during both legs:
  `b299a842ed393d95367a4b0a77e410f71206bd2c`;
- vLLM: `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`; and
- local model aggregate manifest:
  `45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac`.

All live model reads and evidence writes used internal NVMe/ext4:

```text
/mnt/fast-ai/llm-models/laguna-s-2.1
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1
```

The external Corsair USB remained backup-only.

## Evidence and seal

Canonical artifact root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-recovery-abba-8936aac-c59aaad-20260723T131632Z
```

Key hashes:

- A1 evidence manifest:
  `fd5c2e33b90ab29875e8fc6d67b4d3bd60e2514e216179ae5dfe2ee41c26dcd1`;
- B1 evidence manifest:
  `5a5ae9657095dfe95243850a42a96582e0e862eb3c6fc2760577635d6f565981`;
- final campaign chain:
  `290ed77d762a5e5c52575402d4b583ffebbb2527572b04f0fa8a989b275ec9d6`;
- `phase1-analysis.json` and byte-identical stdout:
  `1e21b57c90dd066c58a637739a723b2de951ae5ba99b43352640289eb34ff0de`;
- `phase1-analysis.md`:
  `5a8e122af2d96fe08afe3a44968adb86d1a0efb243e42433fb94b3dabfe36835`;
  and
- `phase1-analysis.seal.json`:
  `49f352104d37ad1bf134d9e6330390be39408fa96cdc2ae6c5861eeb98c8bc4e`.

Both leg manifests verify. The seal reports `valid=true`, the campaign ledger
and hash chain remain unchanged, and all publication-evidence checks pass.
Postflight found no listener on port 8000, no model worker, kernel taint zero,
and both leg cleanup records at status zero.

Compact tracked packet:

```text
data/laguna-s-2.1-w1-n128-nvme-phase1-failed-stop-20260723.json
```

## Disposition

Preserve N128 as negative evidence and keep N64 as the routed-W1 endpoint
policy. The next clean lane should target shared-expert GEMM occupancy or a
separately preregistered narrower routed-W1 geometry. Do not reinterpret the
cycle saving as permission to rerun this campaign or stack the failed router
candidate.
