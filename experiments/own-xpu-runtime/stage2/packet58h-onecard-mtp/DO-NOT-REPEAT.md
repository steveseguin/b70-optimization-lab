# Packet58h do-not-repeat

| Date / arm | Outcome and evidence | Revisit condition |
| --- | --- | --- |
| 2026-10-18 / one-card IQ3, unchanged one-token draft-HC, 91,392-row shared head, retained 58g cache/admission | CPU no-build. Primary model 24.62 tok/s versus 28.8 required. Resident and shared-cache draft options require about 121.65 GB available host RAM, above every retained admission snapshot. [Exact accounting](FEASIBILITY.md), [reproducer](feasibility.py), [closeout](CLOSEOUT.md). | A new causal M2 mechanism with a credible complete-cycle budget below the 60.27 ms zero-overhead verify limit, plus a complete host budget that fits with reserve and margin. Recheck both gates together before copying/building. |

- Do not count shared cache machinery as shared draft/target expert weights.
  The unchanged draft adds 3,145,728,000 expert bytes somewhere.
- Do not duplicate the head prefix: it can alias existing target rows.
- Do not call the tiny device-only optimistic margin a +20% prediction with
  demonstrated state/cache overhead. Duplicate-route screens do not qualify.
- Do not describe 58g's zero-copy misses as a measured demand-copy path or
  present WS128x timing as a whole-host final result.
- Do not reclaim headroom by changing memory exclusions, swap, page cache,
  cache capacity, KV precision or the reserves. Block57's observed online state
  is a discrepancy, not permission to use more memory.
