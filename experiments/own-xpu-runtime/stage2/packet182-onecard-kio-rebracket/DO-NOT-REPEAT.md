# Packet58as boundaries

- Do not turn this into packet58ar's ordered-publication change. This arm changes the wait mechanism only.
- Never reset the spin budget after a sleep; never remove deadlines, async-error checks or completion error propagation.
- Retain the original 1 ms error-recovery sleep and the original poll in A controls.
- Every arm has resident lookup copies and the exact packet58aj arithmetic/kernel/selection identity.
- No separate smoke or parent-smoke prerequisite: K1a/K1b and exact A0 open the bracket.
- A0 stays in exactness and reporting, excluded only from speed and drift.
- Both B views >=1.005 times every warm A; drift <=3%; 60/60 exact. No inferred device win from CPU tests.
- One fixed fresh whole-host lane-A attempt. No retries, model server, settings or publication here.
- Per-op waits are 600 s; in-run evidence checks have no elapsed-time proof deadline.
- Read sensors through every reset path; retain owner-thread utilization even if the speed gate fails.

## packet171b / packet174 (2026-10-19, inherited references)

- Do not move one-card foreground copies onto the compute queue as `memcpy`
  (packet171b, +0.40% neutral): a memcpy on any queue can be carried by a copy
  engine (UR copy offload).
- Do not kick the maintenance list after fills (packet174, -0.02% neutral):
  fills are already submitted promptly.

## packet176 (2026-10-19)

- Do not attribute the fill-coupled transfer cost to the tail readback from
  `transfer_wall_ms` alone. That field also contains the head token/lookup
  uploads issued right after the fill submission on the same copy engine
  (foreground and maintenance lists share the copy-only ordinal, index 0). Use
  `head_transfer_ms` / `tail_transfer_ms` (packet176 and later streams).
- Packet176's B arm is a compute *kernel* path (stores/loads to USM host
  memory), not a copy command. Do not re-test it as a queue `memcpy` variant.

## packet182 (2026-10-22)

| Idea or reading | What the evidence says | Revisit only when |
| --- | --- | --- |
| Fill pacing / deferral on the kernel-I/O (packet176c) line, resume item (b) | Priced, not built. Filled tokens carry 0.628 ms more wall outside the transfer window than unfilled ones (packet171b real spin streams, A1/A2), i.e. 0.313 ms/token; the kernel-I/O B arm left 0.074 ms/token of the removed transfer unrecovered. Ceiling if fills were free: 0.387 ms/token = +1.42%. Realistic 0 to +0.3% (same bytes; packet174 fill kick -0.02%). Below the +2% chain rule. `evidence/fill-lever-price.json`. | packet182's own B-view `fill_split` shows >= 1.1 ms more wall per filled token than per unfilled token outside the transfer window (>= +2% ceiling). |
| "~1.0 ms/token of wall outside the transfer window (fill cost moved)" | A regression artifact: (0.0666 - 0.0349) ms/MB x 30.63 MB/token, slopes fitted over filled tokens only. Unfilled tokens show the same 0.032 ms/MB slope against the NEXT token's fill bytes: fill bytes track miss intensity; the slope prices misses, not fills. The value was the pre-device packet176 pricing; the device readout printed no B-view slope. | Never quote it as a fill cost. Use `fill_split` / `fill_lever_price` (screen/mechanism.py). |
| packet176 `moved_rule` (every B wall slope > 0.5 x every warm A wall slope) as evidence that a fill cost moved | Fires on packet171b, where nothing moved (A and B both 0.0666 ms/MB). It cannot identify a fill cost. | Do not use it for a decision; the field stays only for comparability. |
| Deriving a one-card chain with the unpatched `ops/onecard_chain_derive.py` | Its flag block lands after `if __name__=='__main__':` in suite_driver.py; window.py runs the driver as a script, so no flag reached the native argv (chain 176-a measured the parent poll/copy line). `--predevice-check` imports the module and cannot see it. | Use `chain/derive_chain.py` (block placed before the entry guard) and always run `chain/script_argv_check.py`; it refuses packet176c-chain on all 5 windows. |
| Leaving v5 or chain evidence untracked and not ignored | On 2026-10-19 21:42 EDT an untracked-file cleanup removed packet176's v5 tree (bracket summary ad74c8ef...), packet176c chain a (except two summaries), packet58aj/58as chain a and packet58as's v5 run tree. Only ignored trees (packet171b's) survived. | Commit summary.json/window.json right after a window; keep the bulky run/ trees ignored (this packet's .gitignore). |
| `onecard-chain-quiet2.sh` / `onecard-chain.sh` during the owner pause | Both delete PAUSE-A and PAUSE-B on success and on every failure path. | Use `chain/p182-chain.sh` (saves, holds and restores; never deletes a PAUSE file). |
| `--postnative-check` on one-card chains on this host | No completed one-card chain tree of this harness exists any more; the check refuses every derived chain. `derive_chain.py` carries packet176c's real-evidence rehearsal only when the derived packet is byte-identical (after identity rewrites) to packet176c-chain in 543 files. | The next completed one-card chain is committed or kept ignored; then run the real check again. |
