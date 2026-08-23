# TP4 nightly target-only natural-EOS final gate: PASS at 71.2933 tok/s

Date: 2026-08-23. This is a new strict final-gate artifact; it does not alter
the historical `71.6741 / 71.5488 tok/s` ignore-EOS diagnostic captures.

## Identity and result

- digest-pinned XPU nightly
  `sha256:bc979d1ba312dc8a666c57a40205f35d7fc5d96b2f7450c2c77f5b3d5243f0e0`;
- Qwen3.8 27B AutoRound INT4 W4A16, target-only, MTP off, F16 KV;
- TP4 on GPUs `0,1,2,3`, XPU Graph on, 32K max model length,
  `gpu-memory-utilization=0.60`, one sequence;
- fresh isolated ext4 cache, 25 unique prompts, each sent once;
- natural EOS allowed, 512-token request cap, return token IDs enabled;
- preferred metric: median of the 99 intervals between generated events 1
  and 100 after TTFT.

The strict gate passed at **71.29326283364946 tok/s** conventional. All 25
rows supplied at least 100 token events and reported known stop/length
reasons. Every cached-token count was zero. Twenty-three rows reached the
honest 512-token cap; `selection--customer-email` stopped at 220 and
`holdout--structured-extraction` stopped at 419. Median TTFT was 90.49 ms.

The legacy inclusive-event field is `72.01339680166613 tok/s`; it is retained
only for compatibility and is not the submission metric.

## Evidence

Raw root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp4-mtp0-f16-graph-natural-eos-fresh-a`.

| Artifact | SHA-256 |
| --- | --- |
| `bench.json` | `8ba2473f3a9c95297ba7a5d7059ba010a13b0ae7b706fae9ed556c834445d422` |
| `identity.env` | `da9cbf355f6522a964e19a358554ffb5ccc4f47d9018564e2c6782c2b50825be` |
| `server.log` | `05a7843c785848a965500b897a7b64d4f475049353d443d07517bbf30cee7fbe` |
| 4,421-file cache manifest | `83aaef6468d0071077b1df100052bce77a34a91d0bff5f8c20b0f45fa8bb828d` |
| `canary.json` | `58b4a91460bb5e1ee2c2547e79a92c66668d1149e37d287993931422bb83f47d` |

## Remaining caveats

This closes the natural-EOS and strict-accounting gate for TP4. It does not
remove cross-boot token nondeterminism, supply the missing real baseline to
the objective battery, or make multi-GPU XPU Graph supported by upstream.
Those caveats remain mandatory. No LocalMaxxing submission was made.

