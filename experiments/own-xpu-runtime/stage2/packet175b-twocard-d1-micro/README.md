# Packet175b: D1 dense-lane scale-word multicast, single-card device micro

Kill test for packet173's D1 lever (`../packet173-twocard-lever-table/LEVER-TABLE.md`,
packet140 N1): same-bit scale-word sharing inside the `dense_lane` of the large dense
GEMVs. It runs on packet175's committed harness (commit `012f6f810`, sealed `96dc6e147`),
copied here unchanged except for the D1 arm. The packet168 v3 census puts dense_hc at
11.532 ms per body pass, summed over both ranks.

**Decision rule (coordinator hourly review 44).** Weighted dense GEMV time **B/A**:

* **B/A ≤ 0.97**: "eligible for the combined bundle-9 candidate". D1 is then built only
  inside one combined candidate with packet153's static descriptors (+0.35%, exact,
  retained) and D2, never on its own.
* **Otherwise:** "close D1". The analyzer appends a DO-NOT-REPEAT row.

D1 adds no kernels, so its overhead (owner loads, predicates, subgroup broadcasts) is
inside the timed dense GEMV events: B already includes it. Layer weights: 36 GDN and
12 QSA layers, from layers 0 and 3. LEVER-TABLE §(c)4 originally named ≤ 0.95× for D1;
review 44's 0.97 rule supersedes it and is the analyzer's rule. The analysis reports
the ratio, so the old gate can still be read off.

## The D1 variant (`d1_lane.hpp`)

* **Baseline (arm A).** The harness's dense lane (`p68c::dense_lane`, the device form
  of bundle-8's `p33::dense_lane` r5 schedule). Each lane owns eight consecutive weights
  per 256-element iteration and loads its own FP32 scale word every iteration. Adjacent
  lane pairs (Q6_K, 16-element groups) or quads (Q8_0, 32-element groups) load
  identical bits.
* **D1 (arm B).** On the first iteration of each 32-word chunk, lane L loads scale word
  `chunk_base/group + L` once, predicated to `[begin, end)`, so it never reads past the
  range or into another row. Each iteration then takes its scale bits from the owning
  lane with an integer `select_from_group`.
  * Q6_K: one owner load serves two iterations. A K2560 split4 row (parts of 2, 3, 2
    and 3 iterations) needs 6 scale loads per lane position instead of 10.
  * Q8_0: one owner load serves four iterations.
* **Unchanged arithmetic.** The tiles, their order, the FP32 scale bits, every product,
  the add order, the split4 tree and the BF16 boundaries are all unchanged.
* **Where B applies.** B switches every Q6_K/Q8_0 call of the harness's
  `device_lane`. In this M1 harness those are the Q6_K large projections (QKV, gate,
  Q, K, V) and the attention projections, all split4 with 256-aligned bounds.
* **What stays unchanged in B.** These kernels are not D1 sites in the LEVER-TABLE,
  so they are kept in both sums:
  * HC low/inject and gate/mix (p60/p73, `p49c::dense_lane`);
  * the four-member p49d small tuple;
  * the p109 shared down/mix.
* **Convergence.** `begin` and `k` are subgroup-uniform, so every lane takes the same
  branch and reaches each broadcast.

## Measurement (packet175's harness, unchanged)

* **Workload.** The real packet166 M1 launch order, rows 0 and 1 at position 31, on the
  real layer 0 (GDN) and layer 3 (QSA) tensors (including the 512-expert banks) and the
  same reset seed.
* **Cold weights.** Before each row's layer pass, a 256 MiB stream-read interposer
  (class `evict`) stands in for the other layers of the token.
* **Repeats.** 240 interleaved AB/BA pairs per layer.
* **Arms.** A = bundle-8 dense lane; B = D1. The packet175 warm-ahead path is
  compiled in but never enabled (`warm` stays false), so neither arm has `warm`
  events. The analyzer refuses a stream that contains them.
* **Native summary.** It carries `"variant":"d1-scale-multicast"`. The analyzer refuses
  streams without it, such as packet166's and packet175's.
* **Exactness.** The arm-A reference with proof stores must match the inherited
  real-weight oracle. The arm-B proof pass must be byte-identical to arm A in every
  buffer. Every timed pass is compared with the reference outside its timing events.
* **Reported.**
  * the weighted B/A of median dense time;
  * per-layer paired-ratio median, p10, p90, mean and stdev;
  * the changed-class (projection and attention projection) B/A, for information;
  * layer spans;
  * the packet173 census projection.

## CPU gates (no GGUF read)

* **`run_cpu_gates.py`.** The GNU and Intel host builds run with synthetic weights.
  * GNU and Intel traces are equal.
  * Host arms A and B are byte-identical. B uses an exact host emulation of the
    subgroup: lane `src` returns its predicated owner word.
  * All 142 buffers at position 31 equal packet175's own synthetic trace.
  * Both compilers pass the native D1 self-test: 16,096 coverage-proved tiles
    (every consumed word was loaded by its source lane and is the baseline's word),
    and 1,728 random-bit lane sums bit-identical to `p68c::dense_lane`, for Q6_K and
    Q8_0 at K 320 to 12288 with split 1 and 4.
* **Real-weight oracle.** packet175's inherited real-weight oracle (packet166's 138
  position-31 rows, matched by packet166's lane-B device run) carries over unchanged.
  Parents are referenced as `{name, parent_relpath, parent_digest}` in
  `evidence/oracle-inheritance.json`.
* **`check_preparation.py`.** The real reset/arm sequence runs on a CPU transport in
  the shared Landlock sandbox: 964 resets, real sensors, `ionice -c3`. Arm B takes one
  extra preparation step per D1 site, which proves that B traverses them.
* **`rehearse.py`.** Runs:
  * `lanequeue plan` on temporary queue copies for lanes A and B;
  * `run_micro.py --plan` for both lanes;
  * the private report adapter through the real `run_micro.report_completed`, which
    covers both tails, the invalid-oracle refusal and the rejection of packet166's
    real stream and of a warm-ahead stream.
* **`test_analyzer.py`.** 8 tests.
* **`seal_ready.py`.** Writes `READY-FOR-DEVICE.json` last, after the real pin guard
  has checked both proposals.

## Running it

| Lane | Card | Proposal | Job name |
|---|---|---|---|
| A | 0, `0000:23:00.0` | `ops/lane-queue/proposed-p175b-micro-A.txt` | `packet175b-d1-scale-multicast-micro-A1` |
| B | 2, `0000:43:00.0` | `ops/lane-queue/proposed-p175b-micro-B.txt` | `packet175b-d1-scale-multicast-micro-B1` |

Admit **one** of them, on whichever lane is free. The runner refuses a second lane
once either output exists.

The device guards are packet175's: lane reservation, drain permit, fault review and
supervisor.

Limits:

* disk floor 25 GB;
* whole-process watchdog 7,200 s;
* expected time about 15 minutes;
* no retry, no device reset and no server.

Output goes to `evidence/d1-micro-<lane>1/analysis.json`.
