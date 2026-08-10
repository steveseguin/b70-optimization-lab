# Qwen3.6 27B Q8 VDR2 formal c2/near-32K: functional pass, performance fail

## Decision

Bank this sealed run as valid functional and negative performance evidence for
ordinary VDR2 c2 at near-32K. Both simultaneous full-512 streams are exact to
the fresh sequential phase, selected natural-stop retrieval and external
canaries pass, and true two-slot decode occupancy is measured. The primary and
stretch concurrency performance targets both fail decisively. Do not claim the
eight-slot serving objective from this result or rerun the unchanged recipe.

Run:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal3-vdr2-formal-c2-gpu0-near32k-ub1024-20260810T073751.658231543Z`

## Identity and seal

- model SHA-256:
  `f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce`;
- llama.cpp commit: `15586e2d7165570fb3aa7c26e0d442e289ef69de`;
- runner repository HEAD: `de2f76d1871c32ab3771f53e7ba43419ebc1d106`;
- server SHA-256:
  `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`;
- VDR2 runtime manifest SHA-256:
  `4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49`;
- paired-suite SHA-256:
  `053523440e4a23d7f772dec5025fe4831ba33c0a8eaba76795e4ee76718860af`;
- configuration: F16 K/V, `-c 65536 -np 2 --no-kv-unified`,
  `-b 1024 -ub 1024`, continuous batching, flash attention on, DNN off,
  graph off, no speculation, and 32,768 tokens per slot;
- completion marker SHA-256:
  `cf403892cbd1758be5cb88fea707c080a81de3f3064597d7d8f74b012c12f0b4`;
- artifact manifest SHA-256:
  `35b0108d6f65c4e8d5341c8122e3ff0c22586b4d7708f58e1dad9838c0b6082b`;
- validation summary SHA-256:
  `d0ee698e946c4a80742bfed42f778ff6a8b50c1d3542aa5c37446303e787e2e1`;
- concurrent result SHA-256:
  `f2f52f873fc4aef9a69ea5d4b8af89bbbad8c56725c2ce92caf2e715e0e03ce2`;
- sequential oracle SHA-256:
  `7c41f1dadafe53999fea655be2652a4ff223357c9a26d2c845c3d419438b46c8`.

An independent `sha256sum --check artifacts.sha256` verified all `133/133`
sealed artifacts. The completion marker's artifact-manifest and pre-seal
summary links match the hashes above. The repository runtime manifest and
suite independently hash to the values frozen in `run-identity.env`. Both
phases used fresh server launches with the same attested profile, and all
harness-input checks match the initial harness manifest.

## Functional and occupancy result

The concurrent phase is `PASS_ORACLE_EXACT`. Each stream emitted 512 tokens
with `cache_n=0`, and both token arrays exactly equal their fresh sequential
counterparts:

| Case | Slot | Token SHA-256 |
| --- | ---: | --- |
| `q27-q8-lc-31k-middle` | 0 | `9eb40a724468ab30f2d8e2b9b003130a30ceef1242161a4b6b14046ab98a7a6c` |
| `q27-q8-c2-31k-b` | 1 | `32d83955ca35bea7e96f4dd1061551ffd149d449a689b80c3184dede67492e02` |

Selected-band natural-stop semantic retrieval, intrinsic stream/replay checks,
the two local canaries, and the sealed external baseline canary pass in both
fresh-server phases. The concurrent server fully offloaded `65/65` layers,
loaded `30,839 MiB` (`30,796 MiB` over idle), and retained `1,544 MiB` free.

The requests were released with `0.000103284 s` send skew. Both were decoding
together for `46.978258 s`; measured busy slots per decode were `1.94599`.
The server produced `1,024` tokens across `574` llama decode calls, or
`1.783972` predicted tokens per decode. This is a true M=2 occupancy result.

## Performance result

The performance outcome is a target failure, not an invalid packet:

| Metric | Observed | Primary target | Result |
| --- | ---: | ---: | --- |
| Aggregate prompt processing | `598.149228 tok/s` | `>=400` | PASS |
| Aggregate conventional D511 | `10.144217 tok/s` | `>=30` | FAIL |
| Request 0 conventional D511 | `5.185072 tok/s` | `>=13` | FAIL |
| Request 1 conventional D511 | `10.391849 tok/s` | `>=13` | FAIL |
| D511 fairness, minimum/maximum | `0.498956` | implicit in per-request floor | FAIL |

The aggregate D511 rate uses the shared conventional timing window:
`1,022 / 100.747054 s = 10.144217 tok/s`; it is not the sum of the two
per-request rates. The prompt aggregate uses `63,687 / 106.473430 s`. The
concurrent request wall is `155.648581 s`, yielding `6.578923 tok/s` for all
1,024 generated tokens including both first-token intervals.

Per-request timing exposes the imbalance without assigning a cause:

| Case | Native PP | TTFT | D100 | D511 |
| --- | ---: | ---: | ---: | ---: |
| `q27-q8-lc-31k-middle` | `586.338760 tok/s` | `54.899519 s` | `1.697910 tok/s` | `5.185072 tok/s` |
| `q27-q8-c2-31k-b` | `299.197187 tok/s` | `106.473316 s` | `10.254591 tok/s` | `10.391849 tok/s` |

Their request-wall times are `153.453758 / 155.648467 s`, or
`3.336510 / 3.289464 tok/s` per 512-token request.

This sealed packet uses forward case order on GPU 0. It establishes the
observed `0.498956` fairness failure, not whether the imbalance follows a slot,
prompt, or ordering on another card. Both requests are below the `13 tok/s`
primary floor, so that primary failure does not depend on resolving the cause
of the asymmetry.

The stretch gate also fails: aggregate D511 is below `35 tok/s`, and both
requests are below `16 tok/s`. Exact output does not rescue these performance
failures, and the prompt-processing pass does not offset them.

## Cleanup

Both fresh-server phases stopped without a forced kill or survivor. The port
closed, GPU 0 returned `43 -> 43 MiB`, all four GPUs were idle at the sealed
end-of-run check, the model/runtime files were unchanged, and device, server,
and kernel fault scans were clear.

This packet is the comparator for a materially different concurrency candidate.
It does not establish the Goal-3 per-card or eight-slot four-card throughput
target.
