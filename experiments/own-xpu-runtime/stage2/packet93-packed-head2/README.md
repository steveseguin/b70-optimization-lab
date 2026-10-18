# Packet93: packed Q6_K target head, new decode mechanisms

CPU preparation for a microbenchmark-gated experiment. The original diagnostic
micro-B run qualified head-transpose; the restored-tool reseal requires a fresh
micro-B2 run before engine screens. [Reseal and historical evidence](RESEAL.md).
No engine speed claim follows from these artifacts. Production remains the expanded
packet84 selection: wide64 experts, wide HC gate, ordered retirement,
rec-parallel, rank1 draft and 24/24 target layers.

| View | Target-head representation and decode |
| --- | --- |
| production | Unchanged p33 expanded Q6_K head, SG32/WG32 |
| head-plane | Original 210-byte Q6_K blocks; four code bytes decoded together with word masks |
| head-transpose | Same 210 bytes rearranged into code/scale planes; one low-code word and one high-code halfword per lane |

Both candidates preserve decoded FP32 values, the eight-element traversal,
ordered multiply/add chains and adjacent SG32 reduction. The transposed layout
is reversible, including every original scale/code byte. The loader scatters
4096-block chunks into whole-tensor planes; CPU fixtures exercise the full
chunk and a remainder. No integer dot, FMA, lower precision, compressed KV or
prompt reuse is introduced. The unchanged expanded draft prefix is allocated
separately for candidates; target traffic savings are not total-memory savings.

[Diagnosis and offline assembly](DIAGNOSIS.md) explain why this is a new
mechanism rather than a repeat of packet74. Assembly supports fewer decode
instructions and load sites, not a device speed prediction.

CPU evidence:

- [GNU/Intel exact-byte gates](evidence/cpu-byte-identity.json): three views,
  two fresh runs per compiler, 32 cases each, multiple rows and both raw block
  alignment phases. Decoded FP32 values, lane sums, intermediate trees,
  logits and argmax match production bytes; no tolerance.
- [Full-size startup](evidence/full-shape.json): all six view/rank paths,
  allocation and selection refusals, actual selected target-head operation,
  expanded draft prefix and truthful sharing receipt.
- [VRAM admission](evidence/full-shape-admission.json): unchanged 30 GiB arena
  and 1.5 GB margin rules. Target-head allocation saves 317,849,600 bytes;
  separate draft prefix costs 308,904,960; net rank1 saving 8,944,640 bytes.
- [Python gates](evidence/python-tests.json): shared wrapper admission/import
  tests plus direction, micro threshold, runner and selection-consumer tests.
- [Build receipt](build-device-receipt.json), [micro build](evidence/microbench-build.json),
  [seals/plans](evidence/final-check.json), [temporary queues](evidence/queue-plans.json).

The new `head` key is consumed by allocation, loader, dispatch and the native
plan. Legacy K2/submission consumers refuse every new packet selection; this
screen cannot silently become a record bundle. [Tests](test_consumers.py).

[Device handoff](WINDOW.md) · [retention/rebuild](ARTIFACT-RETENTION.md) ·
[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) · [boundaries](DO-NOT-REPEAT.md).
