# Packet58-onecard-cache23-chain boundaries

## Carried one-card rows (packet58as / 171b / 174 / 176 / 182 / 182c / 58-onecard-cache23; unchanged)

- Never reset the spin budget after a sleep; never remove deadlines, async-error checks or completion error propagation.
- Every window has resident lookup copies and the exact packet58aj arithmetic/kernel/selection identity.
- One fixed fresh whole-host lane-A attempt. No retries, model server, settings or publication here; no quiet-host rerun.
- Per-op waits are 600 s; in-run evidence checks have no elapsed-time proof deadline.
- Derive one-card chains with a flag block placed before the entry guard and always run a script-mode argv check;
  never with the unpatched `ops/onecard_chain_derive.py` (chain 176-a measured the parent line). Done here
  (`ops/packet58c23chain-orchestration/derive_cache23_chain.py`, `evidence/script-argv-check.json`).
- Commit `summary.json`/`window.json`/`queue.json`/`*.log` right after a window; keep the bulky `run/` trees ignored
  (`.gitignore`), never untracked-and-unignored (the 2026-10-19 21:42 EDT cleanup).
- Never use the quiet2/onecard-chain scripts that delete PAUSE files; `launch_chain.sh` never touches a PAUSE file.
- Reuse packet182c's engine bytes for a capacity change: impossible (the engine hard-codes the arena); every capacity
  change recompiles the entry TU and re-audits every allocation gate (packet58-onecard-cache23 did; this chain binds
  those bytes).
- Spend physical headroom beyond the cache23 plan (2.0 GB arena, lower reserve or driver allowance): not without a new
  measured lifetime proof and a ruling; the reserve and the 30.5 GB DRM guard are never reduced.

## This packet (2026-10-23, CPU preparation)

| Idea or reading | What the evidence says | Revisit only when |
| --- | --- | --- |
| Run the parent chain argv (`--cache-bytes 21552729600`) on the cache23 engine | Impossible: the engine's host parser refuses it ("single admitted maximum allocation required", first derivation run). The arena literal must change wherever the chain argv/selection is spelled (`suite_driver.py` ×2, `views.py`, `runtime-selection.json`) BEFORE the generator's real-parser gate (`capacity-patch.json`). | Never. |
| Name the orchestration `ops/packet58-…` | The pin guard globs `ops/<prefix>-*` with prefix `packet58` into the closure of EVERY `stage2/packet58-*` packet (packet58-onecard, packet58-onecard-cache23): their future pin audits would see this packet's READY pins as cross-packet mutable. The orchestration is `ops/packet58c23chain-orchestration` and the derive wrapper refuses a non-empty `ops/packet58-*` glob. | Never while `packet58-*` siblings exist. |
| Apply the memory-plan delta before the generator's post-native rehearsal | The only completed one-card chain evidence on this host (packet182c, arena 21,552,729,600) fails `postload_observation` under the 23 GB plan (`cache[0]['bytes'] == M.CACHE_BYTES`). The generator rehearses with the parent plan; the cache23 plan is rehearsed on the screen's real 23 GB WSCREEN census (`evidence/postnative-cache23.json`). | A completed chain with the 23 GB arena exists (this chain): then `--postnative-check --evidence evidence/card0-cache23-a`. |
| Keep the 182c submission notes verbatim plus the capacity sentence | 2,003+ chars (cap 2,000). The carried 58ah a/b disclosure is compacted with every fact kept; notes are 1,936 chars on the synthetic fixture (1,937 on the 58ad replay). A real run's fault counters change the length by a few characters. | Only if a later ledger entry needs more text: drop the stale public-list sentence first. |
| Put the chain output under `build/` | The one-card harness (`queue_runner.py` requires `evidence/card0-<tag>`), the generator and the sealed submission validator register `evidence/card0-cache23-a`; the bulky streams are git-ignored instead. | A harness revision that moves the registered output; not for this chain. |
| Inherited test failures as "known" | 29 submission/composition tests failed on the generated chain flags (fixture without them), 9 `test_ready` tests on the generated `verify_ready` (no `evaluate`), 1 on a missing parent fixture: identical on a packet182c scratch copy. Fixed here (fixture flags, skip decorators with the reason, parent fixtures copied with provenance): 137 tests OK, 9 skipped. | Never leave them failing on a derived chain. |
| Gate receipts with `{path, sha256}` into ops/ or another packet's `screen/` | The pin guard treats them as cross-packet mutable pins (only `evidence/`/`build/` chain evidence with a passed receipt is immutable). Every reference outside this packet is a `{name, parent_relpath, parent_digest}` provenance record, re-hashed by the gates. | Never. |
| The screen's measured DRM peak vs the projection | Loaded lifetime peak 29,988,990,976 B (331 samples), 45.4 MB above the plan's 29,943,603,712 projection and 511 MB under the unchanged 30.5 GB guard. Expected on a fresh chain too; the guard is live. | A chain window trips the guard: stop, record, do not re-partition without a ruling. |

Chain bar: a fresh exact WS128 above 35.92672010504166 (`cmvjejvoi03qcrf0138emu5a6`) and the live ledger is the
only record claim; the screen's +1.72 % admits the chain by ruling, it is not a record. A WS128 at or below the
ledger is confirmation evidence only (the validator and `--update-record` refuse). No cache drops, power changes,
service launches, device execution or host settings are part of this CPU preparation.
