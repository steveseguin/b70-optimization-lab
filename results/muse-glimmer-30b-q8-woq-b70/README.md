# Muse-Glimmer-30B Q8/WOQ on four B70s

## Promoted result

Muse-Glimmer-30B UD-Q8_K_XL with a pretrained BF16 DFlash assistant, TP4 on
four Intel Arc Pro B70 32 GB cards, one active text request. Vision/mmproj was
not part of this result:

| Gate | Result |
| --- | ---: |
| canonical 256, fresh run 1: prose/code/JSON | `71.583 / 106.436 / 122.246 tok/s` |
| canonical 256, arithmetic mean run 1 | **`100.088 tok/s`** |
| canonical 256, fresh run 2: prose/code/JSON | `72.487 / 106.673 / 122.786 tok/s` |
| canonical 256, arithmetic mean run 2 | **`100.649 tok/s`** |
| pooled canonical arithmetic mean | **`100.3685 tok/s`** |
| frozen 15-prompt cold first-100 interval median | **`161.8996 tok/s`** |
| frozen cold first-100 p10 / mean / minimum | `108.5735 / 175.8128 / 82.4699 tok/s` |
| one-sided prompt-bootstrap 95% lower bound | **`127.0819 tok/s`** |
| full-natural completion median after TTFT | `68.5855 tok/s` |

The kernel uses BF16-rounded activations, direct-strided symmetric S8 Q8_0
weights with F16 group-32 scales, F32 accumulation/destinations, and one fixed
width-16 oneDNN primitive for decode widths 1–16. The drafter terminal choice
uses distributed ARGMAX with local-winner reuse. No drafter training was done.

## Claim boundary

This is a declared Q8/WOQ, target-verified result. It is not BF16, lossless, or
universally token-exact. Code and JSON were target/spec token-exact at 256;
prose took a target-approved near-tie branch. The 15-prompt headline is the
preregistered conventional 99-interval first-100 metric. It does not mean every
prompt or every full natural response exceeds 100; canonical prose is 71–72
tok/s and the realistic minimum is 82.47.

The original BF16-only century objective remained unmet. This later
operator-approved no-training compressed-target successor objective passed.
LocalMaxxing approved the conventional cold-suite result as
[`cmss8515c00n0ms01n3begqgg`](https://www.localmaxxing.com/en/runs/cmss8515c00n0ms01n3begqgg).

## Source of truth

- [standalone reproduction](../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
- [closed-lane handoff](HANDOFF.md)
- [validity and quality gates](validity-gates.md)
- [exact commands and identity](reproduce.md)
- [bugs, negative results, and limitations](bugs-failed-paths.md)
- [structured record](../../data/muse-q8-woq-argmax-century-20260813.json)
- [LocalMaxxing payload](../../data/localmaxxing-muse-glimmer-30b-ud-q8-k-xl-b70-tp4-woq-dflash-161tok-20260813.queue.json)
- [LocalMaxxing receipt](../../data/localmaxxing-responses/muse-glimmer-30b-udq8-b70-tp4-woq-dflash-20260813.json)
- [chronological closeout](../../experiments/muse-glimmer-30b-b70/notes/2026-08-13-q8-woq-realistic-century.md)
- [source snapshots](../../patches/muse-glimmer-30b-b70/README.md)

The Muse optimization lane is closed and banked. New work should start in a
separate model lane rather than modifying this record identity.
