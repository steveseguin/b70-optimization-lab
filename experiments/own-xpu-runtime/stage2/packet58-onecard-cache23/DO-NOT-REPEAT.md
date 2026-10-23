# Packet58-onecard-cache23 boundaries

## Carried one-card rows (packet58as / 171b / 174 / 176 / 182; unchanged)

- Never reset the spin budget after a sleep; never remove deadlines, async-error checks or completion error propagation.
- Every arm has resident lookup copies and the exact packet58aj arithmetic/kernel/selection identity.
- A0 stays in exactness and reporting, excluded only from speed and drift. Both B views ≥ 1.005 × every
  warm A; drift ≤ 3 %; 60/60 exact. No inferred device win from CPU tests.
- One fixed fresh whole-host lane-A attempt. No retries, model server, settings or publication here.
- Per-op waits are 600 s; in-run evidence checks have no elapsed-time proof deadline.
- Do not move one-card foreground copies onto the compute queue as `memcpy` (packet171b, +0.40 % neutral).
- Do not kick the maintenance list after fills (packet174, −0.02 % neutral): fills are already submitted promptly.
- Do not attribute the fill-coupled transfer cost to the tail readback from `transfer_wall_ms` alone; use
  `head_transfer_ms` / `tail_transfer_ms` (packet176).
- Packet176's B arm is a compute kernel path, not a copy command; do not re-test it as a queue `memcpy` variant.
- Fill pacing/deferral on the kernel-I/O line: priced +1.42 % ceiling, 0 to +0.3 % realistic; not built (packet182).
  The "~1.0 ms/token of wall outside the transfer window" is a regression artifact; never quote it as a fill cost.
- packet176 `moved_rule` cannot identify a fill cost; the field stays only for comparability.
- Derive one-card chains with a flag block placed before the entry guard and always run a script-mode argv
  check; never with the unpatched `ops/onecard_chain_derive.py` (chain 176-a measured the parent line).
- Commit `summary.json`/`window.json` right after a window; keep the bulky `run/` trees ignored (this packet's
  `.gitignore`), never untracked-and-unignored (the 2026-10-19 21:42 EDT cleanup).
- Never use the quiet2/onecard-chain scripts that delete PAUSE files.

## This packet (2026-10-22/23, CPU preparation)

| Idea or reading | What the evidence says | Revisit only when |
| --- | --- | --- |
| **`cache_cap max23` = 23,049,601,024 B (+1,496,871,424) on the packet182c record line (this screen)** | **Pending device result.** Priced +0.58–0.84 % (wide +0.51–0.99 %) by one-card synthesis 1; built, sealed, READY, not queued. Admitted under packet58x's revisit condition ("new measured lifetime proof and separately admitted policy"): the proof is the 182c chain's 5 censuses + 81 loaded DRM samples (driver overhead 0.60 GB, transient live peak 295,612,132 B, DRM lifetime peak 28,446,732,288 B), the policy is the coordinator's ruling (driver allowance 671,088,640; bound 29,828,911,360; transient 784,567,808; reserve, floor and the 30.5 GB DRM guard unchanged). | The device v5 result: a win (both max23 ≥ +0.5 % over every warm max, 60/60 exact, drift ≤ 3 %, fills/token ≥ 8 % below max) banks the capacity as a composable screen result; a loss or a fills-not-reduced kill closes capacity at 23 GB (do not re-run the same screen); a chain needs ≥ +2 % over every max view and ≥ 36.6452544 tok/s and a separate composite bundle. |
| Spend physical headroom beyond this plan (2.0 GB arena, lower reserve, lower driver allowance) | Not built: the 2.0 GB arena leaves 0.56 GB of the 2.06 GB physical room with the driver already 0.06 GB over its old allowance; the reserve and the DRM guard are never reduced (packet58x/58h rows). | A measured lifetime proof at 23.05 GB (this packet's device run) and a new ruling. |
| Reuse packet182c's engine bytes for a capacity change | Impossible: the engine hard-codes the arena (`require(arena.bytes==…)`) and the bound; a capacity change is a rebuild of the entry TU. The relinked parent objects and the identity test keep `max` byte-for-byte. | Never; every capacity change recompiles `entry-main` and re-audits every allocation gate (packet58x row). |
| Compile this line from a copy that keeps packet176's absolute include paths | Fails: the tracked frozen headers include each other by absolute path, so a header reached by two paths is two `#pragma once` identities (redefinition errors). The copy must rewrite the 79 frozen headers and the 23 native files (`lineage/path-rewrite.json`). | Never. |
| Let the shared `rehearse_entry --report` synthetic boundary carry the per-view capacity identity | It cannot express `max23` (writes `cache_cap max`); `summarize_bracket` therefore checks allocation/started-empty only and `verify_lookup_views` (first on the device path) enforces `cache_cap`/`cache_usable_bytes` per view; proven by refusing packet182's real B views. | A shared adapter that reads the packet's `views.USABLE`. |
| Pin the `build/gnu-host/p58-cache-fixtures` K1 host fixture through a source seal only | The pin guard reads `k1-cpu.json`'s pin of that binary: restore it (79th record) before the seal, or the temporary plan refuses. | Never; keep it in `restore-inputs.json`. |
| Chain tooling in this packet | Not carried (packet182's `chain/`); the chain bar is not expected and a chain is a later composite bundle (ruling). | A screen result ≥ +2 % over every max view. |

All packet58x lifetime caveats remain. No MTP, route or recurrence retuning, compressed KV, prompt reuse,
frequency prefetch or changed arithmetic is introduced. Parents, screen trees and live queues stay frozen.
No cache drops, power changes, service launches, device execution or host settings are part of this
CPU preparation.
