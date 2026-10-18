# Packet121: reuse the capture table on a miss

CPU preparation only. No device run, speed result, or promotion is claimed.
The [budget and ranked levers](BUDGET.md) use the existing 1,188 lane-A
intervals. The top candidate removes one descriptor-table upload from each
restore. It does not remove any restored byte or change target arithmetic.

This is a private copy of packet118's native sources. The optional selection
key `restore_table=production|p121` selects the old or reverse-table transport.
All eleven old choices and every draft choice stay fixed. Both views use
packet118's 80,128-row prefix and split-head configuration, full BF16 KV and
the `iq3-p49-split32-v1` oracle. The budget's older packet97 + tile16 timing
identity is explicitly separate.

The new code is in [p121_reverse.hpp](p121_reverse.hpp),
[strict_snapshot.hpp](strict_snapshot.hpp), [main.cpp](main.cpp) and
[p49d_submit.cpp](p49d_submit.cpp). Every restore still passes the original
CopyEngine checks, then compares each admitted physical range against the
capture table. Ordinary extents form a prefix; proved spare-bank extents form
a suffix. A normal redo restores the prefix, and abandoning it restores the
suffix before any observer. Backup offsets, byte counts, target math, verifier
and bank ownership remain unchanged.

The local [v5 wrapper](v5/) derives from packet119's fixed one-load wrapper;
its drain fix and pre-exec getrlimit guard remain. The new switch affects only
restore transport. There is no new device allocation. The final CPU seal binds
both exact configurations, native artifacts, selected startup checks, byte
tests, wrapper dependency closure and refusal tests. Adding another config
filename cannot bypass it.

## CPU checks and reproduction

Use `nice -n 19 taskset -c 8-15,24-31 python3 -B` for every command below,
with stdin from `/dev/null`. The CLI builders alone apply the 8 GiB address
limit. Runtime imports never install that cap. Packet94's compiler-turn lock
serializes compilation and waits out whole-host GPU windows.

1. `v5/build_engine.py`: GNU host and Intel device compilation, no execution
   on a device. The unchanged arithmetic objects are pinned packet118 inputs.
2. `v5/miss_gate.py`: the actual miniature target and snapshot code, GNU and
   Intel CPU builds, both views twice. Full canonical mutable-state bytes,
   all 32 position residues and context boundaries, forced cancellations,
   hits, corrected misses, terminal and abandoned redo, consecutive bank/history
   states, unaligned tails and a stale-pointer refusal are checked. This does
   not substitute for real-model device parity.
3. `v5/full_shape.py`, `v5/reset_gate.py`, `v5/protocol_gate.py`,
   `v5/chain_startup.py`: production-shape constructors and captures with mock
   allocations, real CPU reset bytes and native IPC, two fresh brackets versus
   the frozen parent, all eleven inherited chain startup paths for both views.
   The tiny MTP happens to hit throughout; a separate scripted native request
   forces every guess wrong and must preserve every target token and state.
4. `v5/exec_gate.py`, `v5/test_v5.py`, `v5/test_smoke.py`: limit, selection,
   source-binding, drain and smoke-admission refusal checks.
5. `v5/cpu_seal.py --operator-evidence evidence/cpu-byte-identity.json`
   (pass that argument as the full packet-relative or absolute path), then
   `v5/queue_plan.py`. The planner writes new proposed files and plans temporary
   queue copies. It never updates a live queue.

Completed receipts live in [v5/evidence](v5/evidence); the overall preparation
status and test corrections are recorded in the
[work note](../../../../notes/2026-10-18-own-runtime-packet121.md).
Missing or changed evidence makes the seal refuse. Reproduction requires the
frozen parent objects and pinned lab inputs; this is not a public model recipe.

## Device proposal

See [PREREGISTRATION.md](PREREGISTRATION.md). A three-view 64-token smoke must
pass before the five-view 128-token bracket. Both use all twelve fixed prompts
and an extra separately reset incident request per view. Each job loads the
model once, resets every mutable target/draft byte between requests and views,
and drains once. No prompt, KV or response reuse. Device execution belongs to
the coordinator and is not part of this CPU-only task.

The proposal is a diagnostic screen. A positive result requires subsequent
fresh-server quality and performance gates; it is never a record by itself.
The [negative ledger](DO-NOT-REPEAT.md) and eventual preparation closeout retain
the scope and remaining checks.
