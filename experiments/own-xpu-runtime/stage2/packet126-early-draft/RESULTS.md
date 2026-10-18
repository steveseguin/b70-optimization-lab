# Packet126 dependency simulation and admission decision

Both lanes have 12 requests × 99 intervals: **932 hits and 256 misses each**.
All original requests passed their recorded exact oracle and report
`cached_tokens=0`. They are 128-token screens, not the strict512 final gate.
These are measured common-clock command envelopes, not separate GPU kernel
times or the class-balanced headline metric.

| Measured quantity, ms | A hit | A miss | B hit | B miss |
| --- | ---: | ---: | ---: | ---: |
| Emission interval | 14.858069 | 25.665981 | 14.960747 | 25.803577 |
| DRAFT | 1.586452 | 1.586948 | 1.604737 | 1.604953 |
| Rank1 target B, including head wait | 13.252444 | 13.293737 | 13.335624 | 13.383911 |
| Next rank0 speculative A | 12.774485 | 12.771506 | 12.853387 | 12.848083 |
| Rank0 restore R | 0 | 0.558178 | 0 | 0.559249 |
| Rank0 correction C | 0 | 11.801247 | 0 | 11.846807 |

The event DAG reproduces all **2,376 intervals** to below 1e-7 ms. This is
accounting validation, not independent predictive validation: the measured
signed control remainder is retained. The first99 windows keep the actual
next DRAFT command (`D_next`), including its finite-window boundary difference.
They exclude prefill startup and response termination on both schedules;
no latency claim is made for either boundary.

## Simulation and uncertainty

For a coarse host dependency decomposition let T be body/hidden readiness,
H the local head tail, S the remote suffix service, and A the next speculative
half completion, relative to the shared target-half start:

```text
current target completion = max(T + H, max(A, T) + S)
draft before publication  = max(T + D_next + H, max(A, T + D_next) + S)
publish before draft      = max(T + D_next + H, max(A, T) + S)
draft before merge        = max(T + H + D_next, max(A, T) + S)
```

The candidate interval starts with zero additional D on a hit; on a miss it
starts with `max(corrected D, R+C)`. Then the corresponding target completion
above and original signed control remainder apply. A current interval starts
with `max(D,R+C)`. D moves across the emission boundary on hits, but a wasted
D remains on misses. No draft backup/restore, new mailbox or extra control
cost is charged: this is optimistic about new implementation costs. Target
and draft arithmetic/acceptance are assumed unchanged, not qualified here.

The simulator constructs explicit T/H/S witnesses with the **same measured
B and A**, but different rank1 merge waits W. These witnesses are not
estimates of T, H or S. Both zero wait and 0.6 ms wait reconstruct every
current interval. Their opposite admission decisions show that command times
alone cannot decide the favorable reordering. The target head has 202,240
rows on rank1 and 46,080 on rank0. No unknown time is derived by scaling those
row counts or the historical 1.4 ms head timer. The draft prefix stays 80,128.

| Assumed recoverable wait W per interval, **not measured** | Modeled change A | Modeled change B |
| --- | ---: | ---: |
| 0 ms | −1.9517% | −1.9622% |
| 0.2 ms | −0.8201% | −0.8381% |
| 0.4 ms | +0.3379% | +0.3120% |
| 0.6 ms | +1.5233% | +1.4892% |

All three candidate orders agree for these constructed decompositions. This
is a property of these witnesses, not general schedule equivalence. The JSON
retains every dependency and start/end time for example DAGs. Rates are pooled
first99 interval rates, not predictions of the class-balanced headline.

With W=0, modeled A hit/miss means are **14.857468 / 27.255837 ms**; B is
**14.959320 / 27.415335 ms**. Tiny hit changes come from D_next versus D,
not a steady-state saving. Discarded draft costs average
**0.341969 / 0.345849 ms per interval** on A/B. To clear the owner's 0.5%
throughput gate this optimistic uniform-W model needs **0.427631 ms on A
and 0.432252 ms on B**, plus implementation overhead. These thresholds
are calculations, not measurements or achievable bounds.

Rank1's separate site and timing files are empty. Head transfer logs have
durations but no request/position/common-clock boundaries. They cannot tell
whether prefix compute or suffix reply limits each merge. `B−A` includes
suffix service and retirement and is not W. Treating unknown W as zero or as
the full apparent tail would force an unsupported conclusion. Actual sign
and size remain unknown; the supported ≥0.5% build gate is **not met**.

## Prior arms and safeguards

All **141 existing repository DO-NOT-REPEAT indexes** were snapshotted and
scanned. `prior-audit.json` retains every path/hash and draft/head/state
matches, including empty match sets. Relevant distinctions:

- Packet79 moved drafting to rank0 and lost. This proposal keeps it rank1;
  no reverse-hidden transfer or rank0 draft is added. Packet85's matched
  first99 accounting reports −2.109% / −1.114% for its placements; the
  negative index records rounded screen losses of −2.3% / −1.3%.
- Packet106/106b split draft rows across cards on verified hits. The combined
  B result was 55.699237 tok/s versus 56.064003 for the stronger control and
  56.271264 for head-only: −0.6506% and −1.0166%. This proposal leaves draft
  rows and location unchanged and speculates on its input token instead.
  `prior-results.json` retains exact rates, comparisons and source hashes.
- Depth-two packet71c paid recursive draft passes, feedback and M2 target
  tiles; its matched first99 loss was 46.758%. None is proposed here. Letting
  rank0 hold two unresolved target candidates would still require a separate
  state proof and is not admitted by the current one-candidate controller.
- Packet36 records the guessed-embedding draft-cache hazard and requires a
  separate rollback design. The [proposed transaction](README.md) addresses
  that requirement; no unsafe reuse is implemented.
- Packet123 found the same missing split-head timing. Its apparent rank0
  tail is neither free compute time nor measured recoverable head wait.

If revisited, record common-clock body/hidden-ready, prefix-ready, suffix
entry/exit/reply-ready, merge entry/exit, and draft issue/result timestamps,
bound to request/position/sequence. A CPU implementation must then preserve
the drain fix and getrlimit pre-exec gate, pass byte/state/controller/startup/
seal checks, and prepare a 12×64 exact smoke before a v5 bracket (or v4 if not
switchable). Only new proposals and temporary queue planning are allowed.
No build or proposal is made under an unestablished threshold.

## Reproduce and retain

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet126-early-draft/simulate.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet126-early-draft/audit_prior.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet126-early-draft/test_simulate.py </dev/null
```

Eight analysis tests check interval arithmetic, miss work, finite-window draft
indexing, dependencies/single-CCS ordering, byte-preserved methods, import-safe
limits and refusal to promote assumed waits. They are **not** runtime byte
gates, controller correctness, startup qualification or a smoke. The read-only
packet124 parent drain scan passes (`drain-parent.json`); no copied runtime or
new runtime seal exists.

`inputs.tar.gz` is 1,516,198 bytes; `prior-inputs.tar.gz` is 2,671,255 bytes.
Both exceed 1 MiB intentionally: original-byte receipts, not just hashes,
are needed to reproduce the diagnosis from Git. The first preserves both
current summaries, source and negative indexes; the second preserves four
packet106b summaries, packet85 analysis and the head partition header.
Every original and archived member was byte-verified before writing; replay
checks verify them again. No originals were removed. Read repo-relative
members with `tarfile` or extract to a new scratch directory. No model weights
or build products are included. `intervals.json.gz` is derived, deterministic
first99 accounting; `simulation.json` pins its code/method/input identities.
