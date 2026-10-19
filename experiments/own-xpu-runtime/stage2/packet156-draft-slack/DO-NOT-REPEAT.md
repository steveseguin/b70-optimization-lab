# Packet156 boundaries

Searched all 219 rg-visible repository `DO-NOT-REPEAT.md` files before changes.
[Full path/hash audit](evidence/prior-audit.json) and
[matching lines](evidence/prior-matches.txt) include the other model lanes.
This file is the new result, not part of that entry audit.

| Prior arm | How this proposal differs; retained exclusion |
| --- | --- |
| 79 | Draft stays on rank1; no relocation, reverse-hidden dependency or full-head copy. Rank0 placements lost 2.3%/1.3%. |
| 101 | No attention/HC geometry retune or reapplication of already-selected kernels. Prefix remains the bundle8 80,128 rows. |
| 106/106b | No draft-head partition or suffix dispatch. 106b's draft split lost; the +0.36% was its target-head-only split, not the draft. [Measured note](../../../../notes/2026-10-18-own-runtime-packet106b-grid-result.md). |
| 108 | No INT8 load8 micro retry; same branch arithmetic is only rescheduled. Its old draft duration does not price current exposed work. |
| 122 HC/budget | No HC mapping/fusion retry. Historical norm+projection events exclude copy, host work and current idle slack, so cannot certify the complete branch ceiling. |
| 126 | No guessed-token draft transaction, embedding, merge_add, cache/position advance or second unresolved target. Packet154 satisfies the need to locate exposed draft work; sufficient suffix slack is a separate condition. |
| 129 | No precision, expert format or independent acceptance change. |
| 146 | No history lookup, learned proposal, response or prompt reuse. |

| Date | Closed arm | Evidence and reason | Revisit condition |
| --- | --- | --- | --- |
| 2026-10-19 | Hidden-only draft staged at the existing host boundary after prefix drain, while awaiting the same suffix | [Closeout](ANALYSIS-CLOSEOUT.md) and complete command-correlated replay: even crediting required pack/export and misses as free overlap is below the requested +2% bound. No implementation/device screen was admitted. | New current-line evidence supporting at least 0.423078 ms/hit net hidden-branch saving in a legal idle window. An earlier device-queued boundary is a different design and needs its own producer/completion evidence, exact ownership proof and both-lane proposals. |

Do not equate rank0's 1.227 ms draft overlap with rank1 suffix idle time.
Do not claim every individual window is small; retain the rare long outlier.
Do not infer hardware completion time from host drain return. A closed
host-insertion mechanism does not close the draft optimization lane.
