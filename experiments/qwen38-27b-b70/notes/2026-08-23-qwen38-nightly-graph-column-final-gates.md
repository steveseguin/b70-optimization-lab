# Nightly graph column strict final gates: 30.31 / 49.02 / 71.40

Date: 2026-08-23. This closes the natural-EOS and non-vacuous baseline
battery gates across valid TP sizes 1, 2, and 4. It does not rewrite the
historical ignore-EOS diagnostic captures.

| TP | GPUs | strict conventional tok/s | natural-EOS rows | baseline battery | cache postflight |
| ---: | --- | ---: | --- | --- | --- |
| 1 | 0 | **30.310675** | 25/25 | 24/24 comparisons | 1,097 files unchanged |
| 2 | 2,3 | **49.019651** | 25/25 | 24/24 comparisons | 2,277 files unchanged |
| 4 | 0,1,2,3 | **71.293263 / 71.398430** | 25/25 both | 24/24 comparisons | 4,421 files unchanged on replay |

Every row used MTP off, F16 KV, XPU Graph, 32K max length, one sequence,
unique cold prompts, returned token IDs, natural EOS, and the conventional
median of 99 intervals between generated events 1 and 100. Every cached-token
count was zero. Each topology passed the seven objective canaries, 8-run
same-server repeat, and 8K needle against an actual prior known-good quality
JSON; the comparison sets were nonempty and all true.

TP1/TP2 each had one natural stop at 218 tokens and one at 419; TP4 had stops
at 220 and 419. All other rows reached the honest 512-token cap. No response
ended before the metric window.

## What this closes

- The graph speed column is replicated and strict-gate qualified at every
  valid TP size. TP3 remains architecturally impossible because 16 GDN K
  heads are not divisible by 3.
- Natural-EOS policy, strict event/interval accounting, cache-zero evidence,
  full token capture, and non-vacuous baseline batteries are complete.
- TP1 and TP4 are ready for a human outward-submission decision. TP2 does not
  beat the promoted 50.2 tok/s llama.cpp TP2 target-only result.

## What remains disclosed

- Full outputs are not runtime-token-deterministic. TP4 fresh and exact-cache
  replay matched 21/25 despite an unchanged cache manifest. Earlier fresh
  TP1/TP2 pairs also showed 19/25-class cross-boot agreement.
- The runtime explicitly labels multi-GPU XPU Graph unsupported/experimental.
- `71.6741 / 71.5488` remains the TP4 ignore-EOS diagnostic ceiling;
  `71.2933 / 71.3984` is the policy-compliant natural-EOS pair.
- No LocalMaxxing submission or other outward-facing action was taken.

## Raw roots and hashes

All roots are under
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/`.

| Root | `bench.json` | `quality.json` |
| --- | --- | --- |
| `tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality` | `a4ed83bded7de63d2fa92d49db3be5f3ce8c60c51d2cd824f9ccb0cc22e21593` | `738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18` |
| `tp2-mtp0-f16-graph-natural-eos-replay-b-baseline-quality` | `a849065a340dd402085281a645ea1d136f98eb2356fedb3f0dea6f8be81ac606` | `0ba49be19bbb081023259ce290f87990d3e26038e461d136862631442a63bc48` |
| `tp4-mtp0-f16-graph-natural-eos-fresh-a` | `8ba2473f3a9c95297ba7a5d7059ba010a13b0ae7b706fae9ed556c834445d422` | - |
| `tp4-mtp0-f16-graph-natural-eos-replay-a-baseline-quality` | `6884fc5f0e014f30b6251d8558783ce2a6d9d8424191a4d0980f2f3c4e4d7872` | `8215fb791e11b3e4c09056b4979c4739d3d855f2086c4786d45f2053c0342488` |

