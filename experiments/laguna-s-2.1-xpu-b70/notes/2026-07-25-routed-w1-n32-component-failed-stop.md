# Laguna routed-W1 N32 component failed stop

Date: 2026-07-25 America/Toronto

Status: terminal component negative under the frozen N32 protocol. No cards
1-3, counters, graph diagnostic, model service, prompt, generation, endpoint
campaign, payload, or submission were run.

## Result

The existing Xe2 N32 policy is bitwise exact in the Laguna routed-W1 path, but
its isolated gain is too small to justify another noisy endpoint campaign.
Card 0 passed every correctness and contract check and N32 won all 31 paired
timing blocks, yet it missed the preregistered component floor:

| Metric | N64 control | N32 candidate | Candidate effect |
| --- | ---: | ---: | ---: |
| Median time per 47-layer W1 cycle | 6.489345 ms | 6.485808 ms | -0.003537 ms |
| Paired median saving | — | — | **0.028110 ms** |
| Mean paired saving | — | — | 0.027036 ms |
| Relative paired-median improvement | — | — | **0.433174%** |
| Paired block wins | — | — | **31/31** |

The required per-card saving was at least `0.20 ms` per 47-layer cycle. The
later four-card aggregate would also have required at least 2% mean relative
improvement. The observed card-0 result is only 14.1% of the absolute saving
floor and 21.7% of the relative floor. The harness therefore reported
`formal_component_pass=false`, and the preregistered early stop closed the
lane immediately.

The difference between the two median arm values is not the paired statistic:
the frozen A-B-B-A analyzer computes each block's control/candidate pair first
and then takes the median of those 31 savings. That paired result is the
declared `0.028110 ms`.

## Exactness and contract evidence

Before timing, card 0 passed 64 changing epochs. After timing, it passed the
same 64 epochs bitwise against their original hashes. Every epoch compared:

- raw local W1 BF16 output;
- BF16 SiLU output;
- unchanged N64 W2 output;
- fixed-order final gathered output;
- N32 repeat determinism;
- input immutability; and
- remote-route scratch behavior.

All seven M=1 through M=7 cases retained N64 and rejected a literal N32 native
dispatch. Deliberate tile 16, tile 129, missing route interleave, missing
W1-only mode, and missing EP4 map calls all failed closed. W2 weights, W2
scales, and the expert map were unchanged across the run.

The earlier two-epoch card-0 smoke also passed. It is support only and has no
timing or promotion value.

## Frozen identity

- preregistration main commit: `69075b84f`;
- sealed gate/analyzer main commit:
  `0461926d0`;
- vLLM:
  `ef334233deabeaeedb607056a2db1c90edb3887c`;
- XPU kernel candidate:
  `a5f99d8ed98c02eef87e29be44a8cd63b1ec9155`;
- `_xpu_C.abi3.so` SHA-256:
  `f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8`;
- candidate `libgrouped_gemm_xe_2.so` SHA-256:
  `8cdada551eab55e55aae2d33d852999df21c816f1f4575a51a259c714c12567f`;
- timing fixture SHA-256:
  `478a23508e635c91fa62ff0a4b737016266bc308e8fe60111e81abad3d47c1f6`;
- candidate tile: literal N32 for M=8 W1 only;
- control and M=1 through M=7: literal N64; and
- W2: unchanged literal N64.

All live inputs, temporary paths, build logs, and evidence stayed on the
internal `/mnt/fast-ai` ext4 filesystem. The external USB was not accessed.

## Evidence

Smoke:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n32-smoke-a5f99d8-0461926d-20260725/card0/result.json
```

SHA-256:
`3dfc8042872d495b419ae011e7f6f714663f774e55d0319ec162bbbbe06bbb18`.

Formal card-0 result:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n32-formal-a5f99d8-0461926d-20260725/card0/result.json
```

SHA-256:
`474adcf7c75d9260cfe5b6ce9f569b9d1ca5f2d27221b90c20ac5d20d252300d`.

Formal stdout is the gate's intentionally pruned timing summary and has SHA-256
`f8378dd9da3575dfbd1fdd7f3eb2b1e580509b6ef9b4f99f8ca6a2c07affd061`.

## Disposition

Preserve N32 as an exact but terminal component negative. Do not run the
remaining physical cards, counters, graph diagnostic, or an endpoint with this
identical treatment. Do not reinterpret 31/31 wins as a promotion signal: the
effect size is below both frozen materiality floors and far smaller than
observed endpoint variance.

The approved public record remains `94.92003934159611 tok/s`,
LocalMaxxing `cmrzrd4tf001ipa013xpx4kid`.
