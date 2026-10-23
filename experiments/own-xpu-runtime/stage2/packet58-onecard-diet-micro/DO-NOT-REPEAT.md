# Packet58-onecard-diet-micro boundaries

Prepared 2026-10-23 (CPU only; no device result yet). 231 `DO-NOT-REPEAT.md` files under stage2 were grepped
(`evidence/do-not-repeat-search.txt`): no row closes an exact instruction diet of the one-card gate/up kernel; the
rows below are carried so no closed mechanism is re-tried.

## Carried one-card rows (packet58ag / 58ah / 58j / 58p / 58v / 58x / 58as / 171b / 174 / 176 / 182 / 182c / 58-onecard-cache23 / -chain; unchanged)

- Never reset the spin budget after a sleep; never remove deadlines, async-error checks or completion error propagation.
- Every arm has resident lookup copies and the exact packet58aj arithmetic/kernel/selection identity (packet58ah).
- Preserve every BF16 round and ordered accumulation; no tolerance gate (packet58ag port rows).
- Down-tile16 must reach the pinned bank before any cache publication; keep the full arena startup/submit gate: a
  miniature fixture alone missed the p28 defect (packet58j). No draft, MTP, compressed KV, prompt reuse or
  CPU-computed expert misses.
- A CPU pass is neither tile16-only device parity nor a speed result (packet58p). No inferred device win from CPU tests.
- Separate copy queue alone does not prove overlap; CPU mocks prove the protocol only (packet58v).
- Never spend physical headroom beyond the cache23 plan; the reserve and the 30.5 GB DRM guard are never reduced
  (packet58x); DRM sizes use bytes/KiB/MiB.
- Do not move one-card foreground copies onto the compute queue as `memcpy` (packet171b); do not kick the maintenance
  list after fills (packet174); use `head_transfer_ms`/`tail_transfer_ms` (packet176); fill pacing closed ≤ +1.4 %
  (packet182).
- Derive one-card chains with a flag block before the entry guard; name chain orchestrations `ops/packet58c23chain-…`,
  never `ops/packet58-…` (the pin guard globs the prefix into every `stage2/packet58-*` closure).
- `cache_cap max23` is the record (36.602512 tok/s); do not re-run the same capacity screen.
- Never use the quiet2/onecard-chain scripts that delete PAUSE files.
- Cold-vs-warm 1.22× is streaming cost; kernel-order weight layout does not fix cold gaps (packet141/142/145);
  do not prefetch next-layer experts before the router (packet125).

## Carried halfcache rows (packet90 / 58ag)

- FP32 weight caches are exact immutable decodes, never compressed weights/KV (packet90). The halfcache table is
  `iq3::half(i)` for every 16-bit pattern (binding 20); the engine's loader admits only finite weight scales.
- The one-card expert kernel is chosen by the `experts` selection key (`wide64+halfcache` → `p58ag::expert`), not by
  the dispatch table; the row stride is 820 B (packet58-onecard-diet: never port a 840-B `p90exp` result as-is).

## Carried diet rows (packet192 / 193 / 194 / 195 / 58-onecard-diet)

- Both record expert kernels are instruction-issue bound (packet192): a premise, never a speed claim.
- exp-diet on the two-card kernel: 0.784× cold / 0.77× warm, byte-identical on every claimed stratum (packet193);
  +1.96 % in the k3x engine (packet194); record bundle packet195. down-diet closed (0.96); exp-act-epilogue dropped;
  `std::bit_cast` byte arrays and hoisted down products closed by the ISA gate; NaN payload order never canonicalised.
- **Do not screen the diet on a non-halfcache gate/up layout** (packet194); **never register `p193_diet.hpp` in the
  one-card dispatch** (packet58-onecard-diet: 840-B vs 820-B rows, FP32 vs table-decoded halves, 19 vs 20 bindings).
- packet193's window stopped on a NaN-payload-order difference of the PRODUCTION kernel vs the host fixture on the
  NaN-only `exceptional` stratum, and left `active-lane-B.json` with a dead owner: here the NaN-only strata are
  compared by is-NaN per word and the lane is released before the exactness gate (README §2.5, §5).

## This packet (2026-10-23, CPU preparation)

| Idea or reading | What the evidence says | Revisit only when |
| --- | --- | --- |
| **One-card exp-diet `p58ag_diet::GateUp` (hoisted `exceptional`, sign after the scale multiply, hoisted effective scales on `p58ag_exp::wide_chains`; table decode, `p58::resolve`, bindings, `p39::validate` unchanged)** | **Pending device measurement.** All three transformations proved bit-exact on this kernel (README §2; grid magnitudes {8,25,43} static-asserted against this tree); GNU twin bit-exact on 1,250 byte rows incl. permuted slot tables and real 820-B rows, 100,000-block stress per profile 0 mismatches; Intel twin equal on every claimed row, NaN-payload-order-only on the NaN-only strata; ISA 15.66 → 12.02 instr/weight (0.767), 0 spills. | The lane-B window: ≤ 0.85× production cold AND warm in both orders with byte identity on every claimed stratum qualifies it for the engine key `expert_gateup=production\|diet` on the one-card record line (packet58-onecard-diet's recommendation 2: K1a/K1b + one-load max23 bracket, ≥ +0.5 % screen, ≥ +2 % and ≥ 37.335 chain); a closed result (above 0.85× cold or warm) is not repeated in this diet form. |
| Read the Intel twin's mixed-profile stress `table_vs_half` count (7,970 chains) as a table-decode defect | Not a value difference: production(table) and production(`iq3::half`) are the same instantiation with a runtime pointer; icpx unswitches the loop and orders the NaN operands differently in the two versions. The GNU twin has 0 such differences; the finite profile is bit-exact on both twins; the stress row now classifies the count (NaN-vs-NaN vs value) and the rebuilt Intel twin reports 0 in both classes. | Never as a kernel defect; a value mismatch there is a kill. |
| Time the micro on direct pointers only | Wrong identity: the record line runs `b.indirect=true` for `expert_gate_up` (`caching()`); the gated strata use indirect identity slots, `warm-direct` is informational. | - |
| Compile while the packet195 chain runs | Refused by the coordinator hold (06:4x UTC): compiles waited for clearance; `units_idle()` also refuses when another host compiler is running (by exact `comm`). | - |
| Treat a NaN-payload-order-only difference (host twin or device) on f2 / exceptional as an exactness failure | It is the compiler's/hardware's operand order of an IEEE op on two NaNs, outside the admissible domain; labelled `nan_claim`, compared by is-NaN per word; recorded, never a kill (packet193's lesson). | A value difference or a status/error byte there is a kill. |

No GPU, `/dev/dri`, systemd unit, PAUSE/STOP/queue file, sudo or secret was touched; nothing was queued, launched,
committed or submitted. Tracked trees of packet192/193/194/58-onecard-cache23/58-onecard-diet were only read.
