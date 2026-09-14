# Retained native stack profile: exact clip, recorder integration failure

One compiled boat42 request reused packet08 PID66846 and all48 qualified blocks.
The application was not reloaded. All four original raw outputs match exactly;
the retained graph evidence, component identities and owner checks pass. The
recorder subsequently failed during output inventory because its unnumbered
run name violates the frozen retention helper's `campaign + '-r'` contract.
No restored request, retry or deletion followed. The client exited1, while the
single bounded15s nonblocking profiler exited0. The application remains idle on
compiled dispatch; queue/kernel postflight clean and no FAULT latch. Original
raw diagnostic media remain for review. [Failure and narrow correction](retained-multiblock-profile-retention-failure-02.md).

The [sealed evidence](../data/retained-multiblock-profile-01/summary.json) includes
559 text files in a258,669-byte gzip archive, SHA256
`b9fc4884f70afd14d6647b4e545abdf6384d75f88018e80fbe51ffaf5e65675b`.
It links the complete screen03 graph/source archive. The read-only
`scripts/export-retained-profile-01.py` revalidated the completed diagnostic's
parity/graph/owner receipts and idle identity; it did not execute another clip.
External evidence directory:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/retained-multiblock-profile-01`.

The [source-aware stack summary](../data/retained-multiblock-profile-analysis-01.json)
selects only Thread66989, the prompt worker:1341 samples with13.41s total sampled
weight. Exclusive categories are598 queue-idle,18 current-block state checks,
25 lifecycle/registry checks,19 receipt/context work,154 compiled/native wrapper
occupancy,3 unknown-leaf and524 other samples. Each sample has0.01s weight.
The profiler's actual log reports6705 samples across five threads and158 sampling
errors. Missing/partial stacks and waits limit attribution; never sum thread
weights into CPU usage or treat sampled occupancy as GPU kernel timing.

The largest nonidle leaf is193 samples at `main.py:402`, which is `gc.collect()`
after graph execution. Another110 samples end at `model_management.cast_to`.
These observations prevent mislabeling all apparent worker activity as sampler
compute. The diagnostic's client-event preview is7.433s, raw archive7.312s and
client completion9.230s; it is instrumented and has no restored paired control,
so no native speed improvement can be claimed.

The trace also samples eager decoder neighborhood-mask construction. Source
inspection must distinguish CPU-to-device tensor construction from the scalar
extent readback and from opaque custom-op dispatch; a stack containing the
generic PyTorch custom-op machinery is not evidence that our RMS wrapper owns
all that time. Next work targets exact geometry-derived mask reuse/construction
and investigates native wrapper overhead. These are source candidates, not
proven speed wins. Keep256×256 final,25frames at24fps, BF16 and8+3 steps unchanged.
