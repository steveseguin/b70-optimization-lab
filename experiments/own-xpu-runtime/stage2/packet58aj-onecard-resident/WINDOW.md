# Packet58aj coordinator handoff — prepared, never queued

Smoke and one-load v5 are complete under packet58ajb. Do not rerun them.
The amended readiness decision replays their original receipts. Wait for the
active packet58ai census and other admitted work to finish, then pause and
drain both lanes and hold the whole host on lane A, card 0. No job is queued
by this handoff. The coordinator captures a fresh fault review before launch.

The five-view order is mapped / resident / mapped / resident / mapped. All
views keep the complete 58ah composition and resident allocations. A0 remains
exact and reported as warm-up, excluded only from speed and drift. Both
resident views must be at least 99.5% of EVERY warm mapped control;
all sixty responses must match packet49 exactly. This is a stability gate,
not a new record. The one-load test warms source pages during lookup copying.

Before the chain, run `seal.py --verify` and
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

## Packet58ajb repair (October 19)

The original smoke failed before its first prefill token completed. Preserve
`screen/evidence/card0-58aj-screen-a/smoke` unchanged. Use fresh jobs
`packet58ajb-smoke-A` and `packet58ajb-v5-A`, writing under
`screen/evidence/card0-58ajb-screen-a/{smoke,resident}`. Neither is queued.
All model windows explicitly pass `--wait-seconds 300`; K1 retains its existing
300-second per-wait ceiling and 900-second total deadline. The whole-model
watchdogs, exact oracle and graceful teardown remain enabled.

The old evidence identifies first prefill, but not the individual event.
The 300-second deadline is a conservative cold-operation allowance, not proof
that a stall has been fixed. The first token writes six phase checkpoints; a
failed wait records its event, phase, token index, copy allocation/size, last
submitted site and elapsed wait. On any repeat failure retain those files and
do not retry. Only the fresh smoke and v5 can qualify the chain.

The CPU probe compiles the real entry with device defines, preserves real argv
and the first prompt token, and runs production prepare/issue paths with a CPU
transport. It uses synthetic packed bytes, the real embedding vocabulary and
a bounded PLE row count. It does not test GPU scheduling or 29 GB memory pressure.
The shared rehearsal's preparation adapter requires ranked argv and cannot
admit this private RoPE table; its WARN stays explicit. The independent local
probe receipt is `evidence/packet58ajb-preparation.json`.

Packet58ajc post-result amendment: the coordinator intended non-inferiority,
not a two-sided band. The original v5 summary is retained unchanged. Its
60/60 exact responses, 0.105% drift and +1.27% minimum gain pass readiness.
A0/B0/A1/B1/A2 were 26.928/31.959/31.558/32.061/31.525 tok/s. This is
readiness only; fresh WS128 must exceed 31.66271941826957 tok/s for submission.
All model windows retain resident lookups and the explicit 300-second wait.
