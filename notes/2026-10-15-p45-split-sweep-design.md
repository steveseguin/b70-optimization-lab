# Packet45 split sweep: design only, 2026-10-15

**Keep 24/24 with draft rank 0. Test 23/25 with draft rank 1 at 4K.**
These are the best admissible choices in the requested 23/24/25 range under this
model. The predicted dr1 gain is about **0.84 ms per hit and 1.55 ms per miss**.
It is a forecast, not a speed result. Device exactness and an A-B-A repeat decide.

The implementation is the **unapplied**
[patch](../patches/packet45-speed5-split-sweep.patch), based on
`eabc1324206442b9ecb6bffd375cd5b4b8c52f3c`. This task changed no file in the live
packet tree, ran no build and executed no device binary. SPEED4's running windows
were not used as completed evidence. The patch does not itself provide a seal.

## Critical-path model

Average rank busy includes wrong speculative halves, redo and drafting. It does
not identify the longest path of an individual hit. On dr0, a completed draft
precedes overlapping target halves; on dr1, the draft can overlap a miss redo.
The native controller ordering is in `native_controller.hpp:86–101`; the rank
receipts expose the command start/completion envelopes.

Let S be rank-0 speculative HALF, A its confirmed redo, T rank-1 HALF, D draft
publication, and R the ROLLBACK envelope. All durations include the observed
host/queue costs; there is no invented device-only layer timestamp.

```text
hit(dr0 or dr1) = D + max(S,T) + calibrated hit residual
miss(dr0)      = D + R + A + max(S,T) + calibrated miss residual
miss(dr1)      = max(D,R+A) + max(S,T) + calibrated miss residual
```

The next rank-0 speculative half can delay observation of rank-1 completion.
That explains the `max`, including dr1's completion lag. The model retains a
separate measured residual for each prompt and hit/miss case. Median residuals
are −0.034/+0.355 ms for dr0 hit/miss and −0.030/+0.236 ms for dr1. Thus it does
not assume that independently aggregated medians sum to a cycle.

These are medians of per-request command means over the emitted window, from
`rank_trace`, joined to `rank*/timings.jsonl`, draft and guess rows:

| Measured run | Split | S ms | A ms | T ms | D ms | R ms | Hit ms | Miss ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SPEED2 dr0 | 22/26 | 16.537 | 15.197 | 21.562 | 2.739 | 1.252 | 24.773 | 41.733 |
| SPEED3 dr0 | 24/24 | 18.177 | 16.626 | 20.037 | 2.728 | 1.521 | 22.732 | 41.284 |
| SPEED2 dr1 | 24/24 | 20.033 | 18.329 | 18.184 | 2.810 | 1.772 | 23.313 | 40.324 |
| SPEED3 dr1 | 24/24 | 20.069 | 18.377 | 18.371 | 2.830 | 1.794 | 22.865 | 40.434 |

Matched-prompt 22→24 differences divided by two give the effective marginal
cost of moving one layer to rank 0: **S +0.836 ms, A +0.713 ms, T −0.760 ms**.
For boundary b, use `S(b)=S(24)+(b−24)*0.836`, similarly for A and T. D is fixed;
R is held fixed in the central forecast. Those slopes are applied separately to
each placement's own measured baseline, preserving its card-pair differences.

**Individual layer costs are not identifiable from these receipts.** The moved
pair was layer 22 (GDN) plus layer 23 (QSA). The proposed 24→23 move transfers
QSA layer 23; 24→25 transfers GDN layer 24. WS128 records whole-half timings,
with empty `sites.jsonl` and null family timing, not layer timestamps. The mixed
marginal is the available estimator, not a claim that QSA and GDN cost the same.
SPEED2→SPEED3 also changed profiling. Dr0 K2 selections changed `hc.a.act` from
packet18 to p42.tiny.range and `hc.f.act` in the opposite direction; dr1's selected
dispatch is identical. These are additional confounders, not a controlled split A/B.

## Predicted 4K performance

Values are calibrated to **SPEED3**, before SPEED4's unmeasured restore saving.
No forecast credits a SPEED4 device improvement. Compute the changed maximum
per prompt; adjust its observed 99-interval duration by its actual hit/miss
counts, then take the median within each class and across class medians. Do not
compute the primary rate as the reciprocal of the two median cycles.

| Draft rank | Target split | Hit ms | Miss ms | Class-balanced tok/s | Interpretation |
|---|---|---:|---:|---:|---|
| 0 | 23/25 | 23.492 | 41.331 | 37.276 | Predicted regression |
| 0 | 24/24 | 22.732 | 41.284 | 38.157 | Measured SPEED3 anchor; retain |
| 0 | 25/23 | 21.972 | 41.237 | 39.081 | Prediction only; fails 4K memory reserve |
| 1 | 23/25 | 22.029 | 38.885 | **39.608** | Recommended new device arm |
| 1 | 24/24 | 22.865 | 40.434 | 38.131 | Measured SPEED3 anchor; matched control |
| 1 | 25/23 | 23.701 | 41.984 | 36.761 | Predicted regression |

For dr1 23/25, independently varying the mixed layer marginals by ±35% and R
by ±0.135 ms gives 21.737–22.322 ms hit, 38.219–39.562 ms miss and
39.038–40.185 projected tok/s. This is a **sensitivity envelope, not a confidence
interval**. Controller drift, layer heterogeneity and dispatch differences can
move the result outside it. The positive dr1 split23 forecast is worth one arm;
the smaller or negative alternatives are not a reason for a broad sweep.

## Memory admission

Capacity is 34,242,297,856 bytes per card; reserve remains **1,500,000,000 bytes**.
The table reports `(capacity − modeled live bytes − reserve) / 2^20` for each
rank. A negative value fails admission. These are allocation projections, not
new residency measurements; live census and driver safety checks still apply.

| Draft rank | Split | 4K r0 headroom MiB | 4K r1 headroom MiB | 4K fits | 32K r0 headroom MiB | 32K r1 headroom MiB | 32K fits |
|---|---|---:|---:|---|---:|---:|---|
| 0 | 23/25 | 1852.52 | 3540.51 | Yes | 1140.27 | 3087.26 | Yes |
| 0 | 24/24 | 778.91 | 4604.60 | Yes | −62.84 | 4216.10 | No |
| 0 | 25/23 | −288.74 | 5668.86 | No | −1130.49 | 5280.36 | No |
| 1 | 23/25 | 5851.93 | 341.54 | Yes | 5204.43 | −176.46 | No |
| 1 | 24/24 | 4778.32 | 1405.63 | Yes | 4001.32 | 952.38 | Yes |
| 1 | 25/23 | 3710.67 | 2469.89 | Yes | 2933.67 | 2016.64 | Yes |

The arithmetic uses the embedded, hash-verified C256 owner censuses in
`memory_plan.py` and packet40's rank0/rank1 launch metadata, without weight reads.
Layer 23 has 1,106,681,302 live bytes and 886,230 snapshot bytes at C256.
Moving it off rank 0 also removes one context-dependent QSA cache from both
target storage and snapshot capacity. Thus QSA counts change from 6/6 to 5/7.
For growth G relative to C256, dr0 gains `1,106,681,302 + 886,230 + 2G` bytes on
rank 0 and spends `1,106,681,302 + G` on rank 1. The exact split23 snapshot base
is **318,188,610 bytes**, recomputed from the preserved allocation/launch inventory.

Layer 24 is GDN: 1,115,963,658 base bytes plus 1,634,304 alternate-bank bytes
on rank 0, plus 1,917,322 snapshot bytes. Hence 25/23 dr0 leaves only
**1,197,234,462 bytes** free at 4K. It needs at least 302,765,538 fewer actual
allocated bytes before it can clear the reserve. Changing a ledger number alone
would be invalid. Right-sizing the currently conservative backup allocation is
a separate possible repair; it is not part of this patch.

For the recommended 23/25 dr1 arm, rank 1 has **1,858,131,808 bytes free** at 4K,
and only **1,314,969,440** at 32K. The proposed parser/admission checks refuse
32K before creating an output directory or reaching device admission.

## Patch contents and validation

The patch enables `--target-split 23` and the chain helper's sixth argument for
both placements, while preserving default 22/26 dr0 and 24/24 dr1 plus explicit
24/24 dr0. Split23 dr0 is admitted at 4K/32K, dr1 at 4K only. New explicit-split
default output names include `-s23` (and `-s24`); explicit output paths still win.
Split25 stays unsupported: dr0 fails reserve and dr1 is predicted slower.
“Fits” in the table is a capacity result, not a claim that split25 is implemented.

Included changes cover the C++ option/split validation, Python/window/helper
arguments, byte-exact memory ledger, narrow source-pinned seal amendment,
historical-proof reuse, fresh plan and mini-state producers, admission tests,
and detached window-admission matrix. The proposed seal requires **120 plan rows,
62 new split23 mini executions, 52 state checks including four negative controls,
9 admission checks, and 156 detached admission checks**. These are required future
counts, not executed gates in this design session. Every previous gate and the
immutable device oracle requirement remain. Arithmetic, dispatch selection,
SPEED4 capture/restore, runtime guards and CopyEngine's limit are unchanged.

The design was checked with:

- `git apply --check` against the current source, without applying it;
- Python syntax parsing of every proposed Python file;
- **9/9 admission tests** executed from an in-memory source overlay, with an audit
  hook forbidding all packet45/packet44 filesystem mutations;
- the four retained SPEED1–4 qualification verifiers against the same read-only
  overlay, plus rejection of an unrelated owner.cpp source change.

Those checks do not compile or qualify the proposed runtime. The existing seal
continues to describe SPEED4; the patch requires new source-bound artifacts and
receipts before a qualifying device run can admit it. Kernel/mailbox layouts
are unchanged; rebuilt binary hashes will change.

Only after the running queue stops and this proposal is selected:

```bash
# Do not run while packet45 device windows are active.
git apply --check patches/packet45-speed5-split-sweep.patch
git apply patches/packet45-speed5-split-sweep.patch
P=experiments/own-xpu-runtime/stage2/packet45-merged3
cpu=(nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B)
"${cpu[@]}" "$P/speed5_prepare.py"
"${cpu[@]}" "$P/speed5_rebuild.py" gnu-host
"${cpu[@]}" "$P/speed5_plan_gate.py"
"${cpu[@]}" "$P/speed5_snapshot_gate.py"
"${cpu[@]}" "$P/speed5_rebuild.py" device
"${cpu[@]}" "$P/speed5_rebuild.py" asan  # existing seal_context.py requirement
"${cpu[@]}" "$P/speed5_finalize.py"
"${cpu[@]}" "$P/build.py" seal
"${cpu[@]}" "$P/test_window_seal_admission.py"
(cd "$P" && "${cpu[@]}" -c 'import seal45; print(seal45.verify_window_admission())')
```

The preparation refuses any base seal other than the pinned SPEED4 receipt;
rebase the proposal if another repair lands. No real-model CPU suite or compiler
matrix is proposed. Device windows W2m, WS, WSs and WS128x remain the exactness
authority, and publication still requires their passing current-identity receipts.

For the coordinator **after qualification**, the new arm is selected with:

```bash
P=experiments/own-xpu-runtime/stage2/packet45-merged3
SUITE=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" \
  2 4096 1 "$SUITE" "$P/build/speed5-c4096-dr1-s23-gpu" 23
```

Use `--draft-rank 1 --target-split 23 --context 4096 --card 2` on the matching
standalone WS128x/WS128 commands, with this arm's prerequisites and dispatch.
Keep OMP_NUM_THREADS=2 and the same fixed twelve cold prompts. Run the existing
24/24 dr0 control on cards 0–1. For attribution, the cheapest confirming comparison
is 24/24 dr1 → 23/25 dr1 → 24/24 dr1 on cards 2–3, same boot/artifacts and fixed
dispatch when comparing phase costs; both arms must still pass their full chains.
If K2 selects different kernels, report that confound rather than call it a pure
split measurement. Do not publish a projection or select only high repeat values.

## Evidence identity

SPEED2 was read at `build/results-9b91d3270/`; the coordinator moved it during
analysis to `/home/steve/own-xpu-runtime-results/packet45/results-9b91d3270/`.
The move is recorded in [the device ledger](2026-10-14-packet45-device-qualification-rounds.md).
All 24 archived request receipts match the retained SPEED3 prechange manifest
SHA256 `98887246da38a5097362b0b5bac0e0d6dd7155d293230eb91d587fd45d71af85`.
The proposed historical seal reader resolves only the three named moved result
roots, and still compares their bytes to the original hashes; no runtime check
or artifact identity is bypassed.

SPEED3 inputs are `build/speed3-c4096-dr0-s24-gpu/WS128` and
`build/speed3-c4096-dr1-gpu/WS128`. All 152 input file hashes, per-prompt fitted
values, formulas' residuals and sensitivity predictions are embedded in the patch
as `evidence/speed5/split-cost-model.json`, explicitly `qualifying:false`.
Canonical 152-file list SHA256:
`099583dbf3ed9a3b27a771dbc4eb423091103f0ec0bfb069c7e8c22860d45174`.
