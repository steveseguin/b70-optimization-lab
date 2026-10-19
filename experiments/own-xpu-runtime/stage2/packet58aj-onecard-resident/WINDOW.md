# Packet58aj coordinator handoff — prepared, never queued

Wait until p153 and p151 have completed their lane-B device runs. Then pause
and drain both lanes and hold the whole host on lane A, card 0. Use the two
proposal files, smoke before v5. Each runs K1a/K1b and one model load, without
restart or retry. The smoke reads its own driver output immediately, checks
real timing rows and completed requests as they appear, and saves
`first-minute-analysis.json`. The final analyzer replays all twelve requests.

The five-view order is mapped / resident / mapped / resident / mapped. All
views keep the complete 58ah composition and resident allocations. A0 remains
exact and reported as warm-up, excluded only from speed and drift. Both
resident views must stay within inclusive ±0.5% of both warm mapped controls;
all sixty responses must match packet49 exactly. This is a stability gate,
not a new record. The one-load test warms source pages during lookup copying.

After smoke and v5, run `seal.py --verify` and
`verify_ready.py --output ready.json`. Require `ready=true`; a preparation
marker alone does not qualify the chain. Keep the whole-host hold.

Use the exact environment-embedded `chain_command` in `ready.json`:

- Unit: `packet58-onecard-58aj-a`.
- Fresh output: `evidence/card0-58aj-a` (must not exist).
- Fresh fault review: `evidence/fault-review-58aj-a.json`, captured by this
  packet's `fault_review.py` immediately before the chain. Its exact path is
  embedded in the command.
- Order: K1a → K1b → KD → W2m → WS → WS128x → WS128, each once, with 90-second gaps.
- Freeze Codex and block compiles **from WS through completion**. No model/GGUF
  or full-shape reads may overlap any one-card timing window.

All model windows explicitly use `--lookups resident`, HC fusion, HC-wide,
wide64+halfcache, other-fusion, ordered foreground retirement, tile16,
overlapped maintenance, zero-copy misses, context4096, full BF16 KV and
target-only greedy decode. Cache allocation and usage are 21,552,729,600 bytes.
Both K1 fixtures must qualify zero-copy. No sparse or streamed fallback.

Each model window requires 98,990,252,032 bytes available, including an 8 GiB
reserve; the host bound is 90,400,317,440 bytes. Resident copies are
29,321,610,240 bytes and pinned experts 48,627,712,000 bytes. K1 uses the
separate 12 GiB admission. The live sensor counts all anonymous memory and
retains the 4 GiB shadow stop. See MEMORY.md for the production-size table.

CPU preparation stops below 27 GB root free. Device admission retains 25 GB
after the declared writes, checked again by lanequeue before START.
The saved payload-size inventory budgets twice the actual predecessor bytes
(62.18 MB for v5 WSCREEN; 32.50 MB for smoke WSCREEN; 397.49 MB for the seven-window chain),
below the requested three-times ceiling. The proposal totals include both K1
fixtures: 78,362,228 bytes for v5 and 48,683,776 bytes for smoke. These totals
are explicit `planned_write_bytes` fields, so lanequeue does not substitute
its generic 1.1 GB allowance. Missing storage is an
admission refusal, not permission to delete evidence or lower the floor.
No subprocess wall-clock timeouts may count a frozen Codex interval.

Only fresh WS128 supplies the new timing. WS128x is exactness evidence.
The pinned predecessor is now 58ah chain b, 31.66271941826957 tok/s,
`cmvekebvh00a0rf01q3v2c3cz`; chain a's 30.050 result and both chains' paging
counts remain disclosed. No best-attempt selection. Strict512 and an
independent second fresh timing remain false. The submission tool prepares
an honest offline payload only; this handoff performs no external write.

Stop gracefully and retain all evidence on failure. No retry, hard kill,
service restoration, GPU reset, reboot or host-setting change.
