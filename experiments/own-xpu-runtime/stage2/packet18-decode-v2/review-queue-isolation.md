# Independent queue-isolation review, 2026-10-11

Reviewer: the independent read-only `verify_queue_isolation` subagent requested
by the owner. No device code, discovery, PID attachment or file write was used
by that reviewer. This record transcribes the review; source hashes below bind
its final inspected code.

**Every accepted event edge crossing queues: `[]` (empty).**

- Engine queue changes drain on the host. Every boundary and return peer copy
  also drains. Retirement synchronizes both shared-context queues before IDs
  disappear. Final card1 commit drains before card0 token readback.
- Owner compute and copy validate both explicit and automatically appended
  dependencies. Foreign-queue dependencies are rejected. Peer copies also reject
  pending work. Current allocation sites label their logical owners consistently.
- Native Context independently derives copy targets from pointer ownership,
  validates all compute bindings, records event queue ownership and rejects
  foreign dependencies in compute, copy and marker paths.
- Adapter, serial Core and packet6–10 GEMV submissions use their selected queue.
  Split-GEMV first/last dependencies and adapter-local dependencies remain on it.
- Shutdown drains first and submits a marker with an empty dependency list.
  Retirement clears both the native event map and owner queue ledger.
- W0 uses the same owner/adapter and shared context. Every peer call drains;
  begin/commit queue changes drain; its 1,000-kernel chains never share events.
  Final review confirmed real boundary field order (active before error) and
  position==1 assertions on both cards.

The review caught and led to removal of an accidental ordinary-output drain,
addition of the final-commit drain, retirement of owner metadata, and conversion
of the remaining tiny RoPE error write to atomic `fail()`. The static build gate
covers ten source invariants. The runtime queue tests cover four rejection and
successful-drain cases.

Resident token completion waits: 16 normally, 18 for retained fixtures. There
are four input/lookup upload waits and twelve schedule waits: begin0→begin1;
begin1→card0; card0→boundary; four inter-copy boundary fences; card1→return;
one inter-copy return fence; commit0→commit1; commit1→readback; readback completion.
Two snapshot D2H waits give 18. Each retirement additionally calls both native
queue waits, yielding 32/36 queue waits and 48/54 total explicit host wait calls.
Load and shutdown are excluded. The mini and short real receipts verify the
counted 18-fixture/16-prefill values; native wait-call totals are source counts.

CPU/source review cannot prove driver event backing, mappings, device arithmetic,
native duration, JIT startup or actual driver memory use. The fault's native
root cause remains unproven; W0 is still unrun.

## Inspected source SHA256

- `main.cpp`: `51b705aaa88af0e1ba09f77d6d469e998730adb1a82af6eee067ede6901d41f8`
- `owner.cpp`: `76b016f25af1be94df839081bd23b75c44195d930d2bf35a5de6e19299bfe906`
- `owner_retire.cpp`: `e35c366f640d8909b519891fa814aa80228b01ce69bd19ccdf00a8d13cae0da2`
- `backend.hpp`: `d1392c8dab066b482f4571a667982ddcd8b1859c007760ba0eea7eab1d050cbb`
- `adapter.cpp`: `d265a002de77efaaf4c97f37d8a0818c7f03f67e4473c8729fdc49b01efc7247`
- `performance.cpp`: `9f0b52da35dff6d71a4f4eea72b0cfee26a9796934aa033295cf73256bca04d1`
- `native.cpp`: `4e8f5683b6ad8fe2a8a9b44fd1a0cba7dfc6c90616eb06cd583bc0d7ba087b8d`
- `canary.hpp`: `d44c9570f97c768c394b2ce7a6164d143812d31356181924061cfd255d36f15c`
- `queue_gate.py`: `fe2e865ce0b8bbe23b99d587e45483e019db1900bd8f93450eb555f8e89047d1`
