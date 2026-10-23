# Packet58-onecard-cache23: one-load expert-cache capacity screen (max vs max23) on the record line

CPU preparation only (2026-10-22/23). No GPU, /dev/dri, service, setting, PAUSE/STOP/queue file,
sudo or secret was touched; nothing was queued, launched or committed. Lane A, card 0, Qwen3.8
Flash-Next 125B-A6B UD-IQ3_XXS (the quantized compressed version), 128-token capped suite, oracle
`iq3-p49-split32-v1`, BF16 KV, context 4096. Parent line: **packet182c** (record chain WS128
**35.926720 tok/s**, LocalMaxxing `cmvjejvoi03qcrf0138emu5a6`), harness copied from packet182
(committed HEAD `8e2a0f604`, `lineage/packet58c23-copy.json`); packet182/182c trees untouched.

## Coordinator ruling (quoted)

> One-card synthesis 1: the record line has no draft and is bound by 48 serial layer bodies; the only
> open lever above the screen bar is expert-cache capacity. Build the 23 GB capacity screen as the next
> one-card packet: the packet182c selection unchanged plus `cache_cap max23` = 23,049,601,024 bytes
> (256-aligned, +6.95 %), switched at the drained view boundary like `18GB|max`, with the device plan
> re-partitioned from the 182c lifetime receipts (driver allowance → 671,088,640, bound → 29,828,911,360,
> transient bounds 2,415,656,960 → 784,567,808 = 2.65× the measured live peak), host backing +1.5 GB.
> This satisfies packet58x's revisit condition (new measured lifetime proof and a separately admitted
> policy). Chain only at ≥ +2 %, not expected; a screen win feeds a later composite.

Synthesis: `packet182c-chain/analysis/onecard-synthesis-1-20261022.md` (lever 1: +0.58–0.84 % priced,
wide +0.51–0.99 %).

## What changed vs packet182 (engine rebuilt; `native-cache23-delta.patch`, 163 lines, 5 files)

| Item | Change |
| --- | --- |
| Device engine `build/device/own-rt-iq3` | **rebuilt**: `083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a` (parent `1b41fb4d…`). Only `entry-main` (device + gnu-host), the preparation probe, the wait tests and the 16 KB K1 wrapper were compiled (76 s, 0 warnings, one compiler at a time through `ops/compile_turn.py`); the 36 frozen packet58j kernel objects, the 28 frozen host objects, owner/owner_retire/p60_submit/p58ag_submit and packet182's `single_device.o` were relinked unchanged from pinned originals (`restore-inputs.json`, 79 records, digests verified; `evidence/build.json`) |
| Self-containment | every absolute include/#line into `packet176-onecard-kernelio/` rewritten to this packet: 23 native files (`lineage/path-rewrite.json`) and the 79 tracked frozen headers (270 occurrences; packet182 inherited them unchanged and never compiled). `rope.bf16` is now read from this packet's frozen inputs (same bytes `92a8f392…`) |
| `native/generated/main.cpp` | one arena of **23,049,601,024** bytes per load (`--cache-bytes`); `--cache-cap 18GB\|max\|max23`; `max` = 21,552,729,600 usable (packet182c's policy byte-for-byte, see identity proof), `max23` = the whole arena; device bound 29,963,128,848 → **29,828,911,360** in `allocate()` and the plan check; boundary record carries `cache_allocation_bytes` 23,049,601,024 and `cache_usable_bytes`; help lists the dimension |
| `native/bracket_table.hpp` | capacity is the view dimension (A0/B0/A1/B1/A2 = max/max23/max/max23/max; smoke S0 = max23); kernel foreground I/O (`spin-kio`) fixed in every row |
| `native/preparation_probe.cpp` | kernel I/O expected in all five views (60 tail stores / 60 head loads); writes `peak_device_bytes`, the allocation and the bound into its receipt |
| `fullshape_submit_test.hpp`, `postload_allocation_test.hpp` | arena literals; the full-shape mock switches `max23` then `max` and checks both usable extents |
| Python harness (`lineage/harness-delta.json`, 46 counted edits) | `screen/views.py` (capacity rows, `ALLOCATION_BYTES`, `USABLE`), `screen/suite_driver.py` (`--cache-bytes 23049601024`, boundary allocation/usable checks, kernel I/O in every view, `s58c23_decision` on every outcome), `screen/compare_bracket.py` (max/max23 order + the decision), `screen/mechanism.py` (`fills_per_token`, `miss_read_regression`), `screen/argument_gate.py`, `screen/startup_gate.py`, `screen/queue_runner.py`/`window.py` (plan 700–1200 s, watchdog 3600 s), `admission.json` + `memory_plan.py` (both copies), tests, root chain harness literals (`runtime-selection.json`, `views.py`, `suite_driver.py`: arena 23,049,601,024 so a later derived chain allocates the same arena) |

### Every literal changed (grep of `21552729600`, `29963128848`, `"max"` before the change)

- native: `main.cpp` 139 (default `cache_bytes`), 276/621 (`"max"` accept lists + `max23`), 277, 280, 627 (arena literal), 628 (`reset_capacity` extents), 889 + 1803 (`29963128848` → `29828911360`), 1902 (help), 2034 (boundary record); `fullshape_submit_test.hpp` 34, 68; `postload_allocation_test.hpp` 46, 88; `bracket_table.hpp` 15, 16, 23, 27; `preparation_probe.cpp` 93, 96.
- Python/JSON: `screen/views.py` (`MAX_BYTES` → `ALLOCATION_BYTES` 23,049,601,024 + `USABLE`), `screen/suite_driver.py` (`--cache-bytes`), `screen/argument_gate.py`, `screen/startup_gate.py` (`cache_allocation_bytes`), `admission.json` (new `admission` block; packet58x block kept as `parent_admission_packet58x`), `memory_plan.py` + `screen/memory_plan.py`, `runtime-selection.json`, `views.py`, `suite_driver.py` (chain argv), `test_resident.py`, `test_admission58e.py` (+ screen copy), `test_memory_plan.py`, `test_memory_sensor.py`, `budget_gate.py`, `screen/test_async_policy.py`, `screen/test_capacity.py` (rewritten), `screen/test_bracket.py`: `98990252032` → `100487123456`, `21552729600` → `23049601024` (allocation) or `USABLE['max']`.
- **Unchanged on purpose**: `18000000000` (18GB usable value, still selectable), `30500000000` (native after-load + supervisor DRM guard, **never lowered**), `1500000000` reserve, `32000000000` floor; `main.cpp` keeps exactly one `21552729600` (the max usable extent).
- **Inert, listed not changed**: `screen/native_source.py`, `screen/capacity_source.py`, `screen/async_source.py`, `screen/seal.py` (the packet58x-line generator/sealer: they read a `sources/` tree that does not exist here and are not on any gate), `host-admission/base-plan.json` (sealed packet58u bundle: `expert_cache_arena` 18 GB is overridden by `admission.json`), lineage receipts.

## Device plan derivation (`derive_plan.py` → `memory-plan.json`; STOP gate: it refuses to build if any rule fails)

| Quantity | Value (bytes) | Source |
| --- | ---: | --- |
| Physical floor / device reserve / DRM guard | 32,000,000,000 / 1,500,000,000 / 30,500,000,000 | unchanged packet58x; guard never lowered |
| Census device total (every chain window identical) | 27,841,904,372 | `packet182c-chain/evidence/card0-182-a/{KD,W2m,WS,WS128x,WS128}/run/run/census.json` |
| Lifetime DRM peak (81 loaded samples: after_load + every request reset, 5 windows) | 28,446,732,288 (27,780,012 KiB, WS128x) | `drm-memory-*.txt` samples (86 incl. 5 `end`) |
| Driver overhead measured | **604,827,916** (0.60 GB) | DRM peak − census |
| Driver allowance | 536,870,912 → **671,088,640** (margin 66,260,724 over the measurement) | ruling; the old allowance was below the measurement |
| Device-owned bound | 29,963,128,848 → **29,828,911,360** | floor − reserve − driver allowance |
| Expert arena | 21,552,729,600 → **23,049,601,024** (+1,496,871,424, +6.945 %, 256-aligned) | ruling |
| Fixed categories (unchanged) | target_nonexpert 5,815,529,984; KV 116,391,936; recurrent 59,019,280; pointer tables 2,359,296; publication staging 1,179,648; half table 262,144 | packet58x; census KV/recurrent equal them exactly |
| Transient measured live peak | 295,612,132 = operator-scratch 268,435,456 + other workspace 27,176,676 (1,952 rows); device transfer-lifetime 0 | census workspace/transaction rows |
| Transient bounds | 1,073,741,824 + 1,073,479,680 + 268,435,456 = 2,415,656,960 → **402,653,184 + 113,479,168 + 268,435,456 = 784,567,808** (2.654× the live peak; each bound ≥ its measured peak; transfer unchanged) | total = bound − 240 − fixed − arena (the ruling's number) |
| Category sum / margin | 29,828,911,120 / 240 (physical margin 0: the bound is the exact remainder) | arithmetic |
| allocate() peak after growth | **29,338,775,796** (margin 490,135,564 under the bound) | WS128 `memory.json` 27,841,904,372 + growth; the CPU probe measured the same 29,338,775,796 at production size |
| Planned peak after growth | 29,338,513,652 | WS128 `plan.json` 475,217,652 + 27,366,424,576 + growth |
| DRM projection after growth | **29,943,603,712** (margin **556,396,288** under 30.5 GB) | lifetime DRM peak + growth |
| Host admission | 98,990,252,032 → **100,487,123,456** (host bound 91,897,188,864 + 8 GiB reserve) | WS128 `window.json` memory_admission + full backing of the growth (packet58x rule); MemAvailable at the 182c WS128 start 120,821,522,432 |

The windows pin ~85 GB of host memory (48,627,712,000 packed experts + 29,321,610,240 resident
lookups + process); the argument gate ran WSCREEN admission with the endpoint-free MemAvailable
(120.6 GB) substituted because the owner's endpoints run during preparation (recorded per window).

## Rows (card 0, lane A; proposal `ops/lane-queue/proposed-p58-cache23-one-card-A.txt`, PROPOSAL ONLY, never queued)

| Row | What | Duration |
| --- | --- | --- |
| `packet58cache23-one-card-v5-A` | K1a, K1b (unchanged fixtures, ~1 min), then ONE load `max / max23 / max / max23 / max` (A0/B0/A1/B1/A2), 12 × 128-token requests per view, no separate smoke (A0 is the exact warm-up) | ~13–14 min (packet182 identical shape: 793 s); plan 700–1200 s; **watchdog 3600 s** (queue row and WSCREEN window); total under 20 min |

Native argv (every view): the packet182c record argv with `--cache-bytes 23049601024 --cache-cap max`
plus the bracket table whose 5th column switches `max`/`max23` at the drained view boundary.

## Decision `s58c23_decision` (`screen/compare_bracket.py`, kept on every outcome)

- **Screen winner** iff both max23 views ≥ 1.005 × every warm max view (A1, A2), 60/60 exact vs the
  oracle (`compare()` raises otherwise), warm drift ≤ 3 %.
- **Chain rule** iff also ≥ 1.02 × every max view (A0 included) and ≥ 36.6452544 tok/s (= +2 % over
  35.926720; the ruling quotes 36.645). Not expected; a chain is a later composite bundle, not this packet.
- **Kill rules**: any inexact view (refused by the checker); DRM total-vram0 > 30.5 GB (native after-load
  guard + supervisor, unchanged); max23 fills/token not ≥ 8 % below max → capacity closed at 23 GB
  regardless of speed; warm max < 35.2 tok/s or drift > 3 % → host disturbed, report, no automatic rerun.
- Reported for both arms: fills/token, fill MB/token, miss-read regression (wall outside the transfer
  window of unfilled tokens vs the next fill boundary's MB, and of filled tokens vs their own fill MB).
  On the real 182c WS128 record stream: 15.449 fills/token, 30.63 MB/token, 0.0322 ms/MB.

## Gates (all CPU; `gates.py --check`)

| Gate | Result | Receipt |
| --- | --- | --- |
| Plan derivation (STOP gate) | passed; no rule fired | `memory-plan.json` |
| Build | 11 compiler/test commands, 76 s, 0 warnings, build tree 81 MB, unit polls empty | `evidence/build.json` |
| `max` byte-identity proof | 583 checks: identical plan/fill/table trace inside the larger arena; max23 keeps more resident (9,216 vs 8,192 scaled); cap above allocation and switch during a position refused | `evidence/cache-identity.json` |
| Production-shape startup, production size, max and max23 | real WSCREEN argv through this packet's device-define probe under Landlock: 5 view resets, 60 requests, 130 reset sensors, 60 tail stores + 60 head loads; probe census peak 29,338,775,796 ≤ bound; DRM projection 29,943,603,712 < 30.5 GB; peak RSS 1.14 GB | `evidence/preparation.json` |
| Real native parser (host binary), max/max23 table + 8 negative cases | pass; `cache_allocation_bytes` 23,049,601,024 | `screen/evidence/startup-cpu.json` |
| Loader / exec limits | ldd of 4 ELFs under the closed env; `--help` lists `--cache-cap 18GB\|max\|max23`; unknown flag and `max24` refused by the parser; RLIMIT_AS unlimited required | `evidence/loader.json` |
| Real launch path to intercepted native exec (K1a/K1b/WSCREEN) | pass; WSCREEN admission 100,487,123,456 with substituted MemAvailable | `screen/evidence/argument-gate.json` |
| Analyzer on REAL evidence | packet182 bracket: 60 exact requests re-checked, packet182 views refused as this candidate, packet176 readout fields identical to its committed summary; packet182c WS128: 12 exact, 35.92672010504166 reproduced, fills/MB identical to the bracket's kernel-I/O views; 7 decision cases | `evidence/analyzer-real-parent.json` |
| Python tests, differential vs packet182 (git-archive copy) | 113 vs 106 tests, 0 new failures, 4 stale failures fixed, 2 inherited failures identical on both sides; 34 policy/decision/unit tests + 27 delta/memory tests pass | `evidence/python-cpu-gates.json` |
| Drain fix | 2 FIXED, 0 UNFIXED | `evidence/drain-fix.json` |
| Seal, proposal, imports, temporary plan, shared `rehearse_entry --report`, pin guard | pass (1,175 sealed inputs; report smoke+bracket kinds; gate identity WARN only) | `evidence/package-rows.json`, `entry-imports.json`, `queue-plans.json`, `shared-entry-report-final.json`, `pin-guard.json` |
| `final_checks.py --ready` | READY written LAST; pin census on the READY closure (0 cross-packet mutable pins required); private-copy `lanequeue.py plan --lane A` | `READY-FOR-DEVICE.json`, `evidence/final-ready-checks.json` |

## Not claimed

No device result, speed or record. The +0.5–1.0 % is a price, not a measurement. No strict512/full512
gate. The shared rehearsal's synthetic boundary cannot express `max23`: the per-view capacity identity
is enforced by `verify_lookup_views` (runs before the summary on the device path) and proven on real
packet182 data (its B views are refused); `summarize_bracket` re-checks the allocation and the
started-empty switch only. intel-host `own-rt-iq3` was not built (no gate reads it). The DRM
projection is arithmetic on the 182c lifetime peak; the native after-load guard and the supervisor
measure it live. Chain tooling (packet182's `chain/`) is not carried: a win feeds a later composite.

[Boundaries](DO-NOT-REPEAT.md) · [Retention](RETENTION.md) · note `notes/2026-10-22-packet58-onecard-cache23.md`.
