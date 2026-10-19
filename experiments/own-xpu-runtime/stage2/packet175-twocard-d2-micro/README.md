# Packet175: D2 dense-weight L2 warm-ahead, single-card device micro

Kill test for packet173's top two-card lever, D2 (`../packet173-twocard-lever-table/LEVER-TABLE.md`).
The packet168 v3 census puts dense_hc at 11.532 ms per body pass, summed over both
ranks (5.574 + 5.955 ms). D2 issues a warm-ahead of each dense GEMV's weights into
L2 before the GEMV. Arithmetic is unchanged.

**Decision rule.** Coordinator hourly review 44 replaced the original 4.8% rule before
this packet was sealed. The rule uses the weighted dense GEMV time **B/A**, with the
warm-ahead kernels' own time included in B:

* **B/A ≤ 0.97** (a reduction of at least 3%): the outcome is "eligible for combined
  bundle-9". D2 is then built only together with packet153's static descriptors
  (+0.35%, exact, retained), never on its own.
* **Otherwise:** "close D2". The analyzer appends a DO-NOT-REPEAT row.

Weights: 36 GDN and 12 QSA layers, from layers 0 and 3.

## Design

* **Code.** `micro.cpp` is packet166's micro (which passed on lane B today), run on
  the M1 path only: rows 0 and 1, one after the other, at position 31. It uses the
  same private native closure (`native/`, `lineage/`), the real layer 0 (GDN) and
  layer 3 (QSA) tensors including the 512-expert banks, and the same reset seed.
* **Dense GEMV classes.** HC low/inject (p60), HC gate/mix (p73), the large
  projections (split4 dense lane plus finish), the small tuples (p49d), the attention
  projection (plus its split-finish combine) and the shared down/mix (p109).
* **Kernel caveat.** The large projections are packet166's lab-owned device form of
  the bundle-8 r5 schedule. That form is byte-checked against the frozen arithmetic
  reference. It is not the `main.cpp` sealed-selection dispatcher itself.
* **Arm A:** baseline.
* **Arm B:** the same launches. Before every dense GEMV launch, one warm-ahead kernel
  per weight tensor that GEMV reads loads one 32-bit word per 64-byte line of the
  whole weight allocation. The loads fold into a store that is never taken, so every
  line passes through L2, and the kernel writes nothing. B is timed as dense plus
  warm.
* **Arm B′:** the warm-ahead kernels' own time, reported separately.
* **Realism of L2 eviction.** Each row runs the real packet166 launch order: HC, the
  projections, conv/recurrence or QSA, the routed experts (10 of 512), the shared
  expert and the combines. Before each row's layer pass, an interposer stream-reads
  a 256 MiB buffer (class `evict`, excluded from the dense sums). It stands in for
  the other layers of the token, so every weight starts cold, as it does in the real
  body.
* **Repeats.** 240 interleaved pairs per layer, in AB/BA alternation.
* **Exactness gates:**
  * A reference pass (arm A, proof stores) must match the inherited real-weight
    oracle.
  * An arm-B proof pass must be byte-identical to arm A in every buffer.
  * Every timed pass is compared with the reference, outside the timing events.

## CPU gates (no GGUF read)

* **Parity.** `run_cpu_gates.py` runs the GNU and Intel host builds with synthetic
  weights:
  * the GNU and Intel traces must be equal;
  * host arms A and B must be byte-identical;
  * all 138 packet166 buffers at position 31 must equal packet166's own synthetic
    trace.
* **Real-weight oracle.** Because the traces match, packet166's agreed real-weight
  oracle carries over to this packet: the 138 rows at position 31, which packet166's
  lane-B device run matched with `cpu_oracle_match` true. Parents are referenced by
  `{name, parent_relpath, parent_digest}` in `evidence/oracle-inheritance.json`.
* **Preparation.** `check_preparation.py` runs the real reset/arm sequence on a CPU
  transport inside the shared Landlock sandbox: 964 resets, real sensors and
  `ionice -c3`.
* **Rehearsal.** `rehearse.py` runs `lanequeue plan` on temporary queue copies for
  lanes A and B, then `run_micro.py --plan` for both lanes. It also runs the private
  report adapter (`report_adapter.py`) through the real `run_micro.report_completed`
  entry. The adapter covers both decision tails, the invalid-oracle refusal and the
  rejection of packet166's real stream.
* **Seal.** `seal_ready.py` writes `READY-FOR-DEVICE.json` last, after the real pin
  guard has checked both proposals.

## Running it

The proposals are `ops/lane-queue/proposed-p175-micro-A.txt` (card 0, `0000:23:00.0`)
and `ops/lane-queue/proposed-p175-micro-B.txt` (card 2, `0000:43:00.0`). Admit one of
them, on whichever lane is free.

* **One lane only.** The runner refuses a second lane once either output exists.
* **Device guards.** The same guards as packet166: lane reservation, drain permit,
  fault review and supervisor.
* **Limits.** Disk floor 25 GB. Whole-process watchdog 7,200 s. There is no per-op
  native deadline, so per-op waits are effectively at least 300 s. No retries, no
  device reset and no server.
* **Output.** The run writes `evidence/d2-micro-<lane>1/analysis.json`.
