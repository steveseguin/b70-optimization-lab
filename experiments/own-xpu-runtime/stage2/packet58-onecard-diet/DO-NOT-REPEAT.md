# Packet58-onecard-diet boundaries

## Carried one-card rows (packet58as / 171b / 174 / 176 / 182 / 182c / 58-onecard-cache23 / -chain; unchanged)

- Never reset the spin budget after a sleep; never remove deadlines, async-error checks or completion error propagation.
- Every arm has resident lookup copies and the exact packet58aj arithmetic/kernel/selection identity.
- A0 stays in exactness and reporting, excluded only from speed and drift. Both B views ≥ 1.005 × every warm A; drift
  ≤ 3 %; 60/60 exact. No inferred device win from CPU tests.
- One fixed fresh whole-host lane-A attempt. No retries, model server, settings or publication here; no quiet-host rerun.
- Per-op waits are 600 s; in-run evidence checks have no elapsed-time proof deadline.
- Do not move one-card foreground copies onto the compute queue as `memcpy` (packet171b); do not kick the maintenance
  list after fills (packet174); attribute fill-coupled transfer cost through `head_transfer_ms`/`tail_transfer_ms`
  (packet176); packet176's B arm is a compute kernel path, not a copy command.
- Fill pacing/deferral on the kernel-I/O line: priced +1.42 % ceiling, 0 to +0.3 % realistic; not built (packet182).
- Derive one-card chains with a flag block placed before the entry guard and always run a script-mode argv check; never
  with the unpatched `ops/onecard_chain_derive.py`. Name chain orchestrations `ops/packet58c23chain-…`, never
  `ops/packet58-…` (the pin guard globs the prefix into every `stage2/packet58-*` closure).
- Commit `summary.json`/`window.json`/`queue.json`/`*.log` right after a window; keep the bulky `run/` trees ignored.
- Never use the quiet2/onecard-chain scripts that delete PAUSE files.
- Reuse packet182c's engine bytes for a capacity change: impossible (arena hard-coded); every capacity change recompiles
  the entry TU and re-audits every allocation gate. Never spend physical headroom beyond the cache23 plan without a new
  measured lifetime proof and a ruling; the reserve and the 30.5 GB DRM guard are never reduced.
- **`cache_cap max23` on the record line: measured 2026-10-23 SCREEN WIN** (+1.72 % over every warm max view, fills
  −12.9 %, 60/60 exact) and **chain 36.602512 tok/s, LocalMaxxing `cmvkcqznb002lng01fsrhjn7t`** (+1.88 % over
  35.926720). Do not re-run the same capacity screen; capacity beyond 23 GB needs a lifetime proof and a ruling.

## Carried diet rows (packet192 / 193 / 194)

- Both record expert kernels are instruction-issue bound (packet192): a premise, never a speed claim.
- exp-diet (`p193diet::GateUp`) on the two-card kernel: 0.784× cold / 0.77× warm, byte-identical on every claimed stratum
  (packet193); in the k3x engine behind `expert_gateup=diet`: +1.96 % screen win, 10.8–11.8 µs per layer, every view
  exact (packet194); record bundle packet195. down-diet closed (0.96); exp-act-epilogue dropped; `std::bit_cast` byte
  arrays and hoisted down products closed by the ISA gate; NaN payload order never canonicalised.
- **Do not screen the diet on a non-halfcache gate/up layout** (packet194): the diet is a diet of
  `p90exp::Kernel<IQ2_S,2560,64,wide>` only.

## This packet (2026-10-23, CPU only; STOPPED)

| Idea or reading | What the evidence says | Revisit only when |
| --- | --- | --- |
| **Register packet193's `p193_diet.hpp` (`p193diet::GateUp`) as-is in the one-card expert dispatch behind `expert_gateup=production\|diet`** | **Impossible by layout** (`evidence/layout-mismatch.json`, `evidence/compiler-proof.json`): the header binds through `p90exp::Kernel::bind` (rb = `p90::expert_stride(2560)` = **840 B**, FP32 halves at `halves+4*step`, direct pointers, 19 bindings, `p90exp::validate`); the one-card record kernel is `p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached>` on **820-B** `p49bgemv` rows with 16-bit halves at `halves+2*step` decoded through the 65,536-entry halfcache table (binding 20), rows reached through `p58::resolve(..., b.indirect)` expert-cache pointer slots, `p39::validate`. A registration would be refused by the validator or read the wrong bytes. Nothing was built. | Never as a copy of the header. A one-card diet is a **new kernel** (`p58ag_exp` with the same three transformations, keeping the table decode and the slot resolution) with packet193's full proof chain (ISA gate, GNU+Intel twins at production shape incl. halfcache/indirect strata, lane-B device micro ≤ 0.85× with byte identity) **before** an engine key and a one-card screen. |
| Read "the kernel dispatch tables of packet182c and the packet190 k3x selection are byte-identical" (one-card synthesis 1) as "the same expert gate/up kernel" | Wrong: that table is `dispatch-speed6.json` (22 `packet26.dispatch.v1` classes; the only ffn entry is `ffn.combine`). The expert kernel is the `experts` selection key: `wide64+halfcache` → `p58ag::expert` on one card, `exp-halfcache` → `p49d::expert` Arm 10 on two cards; the two lines store expert rows in different byte formats (820 vs 840 B). | Never; check the `experts` key and the row stride before porting any expert-kernel result between the lines. |
| One-card exp-diet (`p58ag_diet::GateUp`, the three transformations on `p58ag_exp::wide_chains`) | **Pending, not built.** Priced at the brief's 11.4 µs per layer = +2 % (48 serial layer bodies); packet194 measured 10.8–11.8 µs on the two-card kernel, but the one-card kernel pays a table gather for `d` and a slot resolution that the two-card count does not, so the saving must be measured in a micro first. | A packet193-shaped micro on lane B qualifies it (≤ 0.85× cold and warm, byte-identical on every claimed stratum incl. halfcache/indirect strata); then this brief's engine screen. |
| Compile anything while `pgrep -f icpx` reports 1 | That count was this shell matching its own command line (memory: process checks must not self-match). Use `ps -eo comm=` and match `icpx`/`clang++`/`ld`/`sycl-post-link`/`ocloc` exactly; 0 were running (`evidence/compiler-proof.json`). | — |

No GPU, `/dev/dri`, systemd unit, PAUSE/STOP/queue file, sudo or secret was touched; nothing was queued, launched,
committed or submitted. No proposal and no `READY-FOR-DEVICE.json` exist for this packet.
