# Packet170 do-not-repeat

| Date / arm | Binding outcome | Revisit condition |
| --- | --- | --- |
| 2026-10-19 / packet58aj one-card MTP, historical resident INT8 draft and packet166 causal class ratios | **Close without a build.** Current M1 class shares are unavailable; a conservative complete V2/cache/feedback/state cycle is unsupported. +3% at a=.787 requires C≤54.273508 ms, or V2+F+S+E≤51.159824 after D, rejection and one publication. Conditional charged sensitivity is 63.613909 ms; it is not a bound or measurement. Memory arithmetic fits only after paying for reduced target cache (18.216 GB resident case); required host 103.314 GB fits even with all five excluded blocks debited. [Analysis](README.md), [source-bound numbers](cycle.json), [closeout](CLOSEOUT.md). | New evidence for the missing current-line class shares and a distinct causal mechanism supporting the full cycle under the threshold, including wrong-row routes, smaller-cache service, one-card draft feedback/repair and exact target state selection. Recheck against a drain-free plain baseline if it exists; retain 1.5 GB device reserve, host exclusions/margin/reserve, BF16 KV and iq3-p49-split32-v1. |

- Packet166's weighted device ratio multiplied by full wall time is not a
  complete-cycle proof. Its class ratios do not create missing 58aj shares.
- Do not substitute CPU expert execution time for GPU zero-copy miss latency,
  fills for misses, or replayed hit rates for native measured cache-size data.
- Do not count route union twice or add full M2 miss cost on top of an already
  multiplied baseline miss component.
- Do not retain the full target cache beside the resident draft, or give the
  shared-cache draft both free residency and zero target pollution.
- Do not set unknown feedback, successful-prefix selection, embedding/PLE,
  head or exposed host work to zero. Favorable sensitivities are not a gate.
- Keep all earlier exclusions in [the full audit](dnr-audit.json) closed.
- This closes the submitted evidence-based build proposal, not all one-card
  MTP designs or the model's optimization lane.
