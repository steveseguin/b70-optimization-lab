# Packet58ad: one-card HC-fusion record chain

Prepared ahead of packet58ab's smoke and five-view bracket. This packet vendors
packet58z's seven-window chain. It reuses packet58ab's finished native binaries
by SHA-256, without rebuilding. Nothing is queued, launched or submitted here.

The fixed configuration is `--hc p60fusion`, tile16, overlapped maintenance,
21,552,729,600 cache bytes allocated and used, zero-copy misses, host-pinned
experts, BF16 KV, context4096, and target-only greedy output. Packet58ab's exact
tile16 selection JSON stays unchanged: its separate native `--hc` flag chooses
the HC implementation. The oracle stays `iq3-p49-split32-v1`.

Pinned predecessor: **29.259764156562692 tok/s**, `cmvebtu5f009frf01gsnfi2eh`,
read from `record-threshold.snapshot`. No new measurement is claimed.

## Readiness and launch

`verify_ready.py` recomputes qualification from finished packet58ab receipts,
using a private copy of its reader. It verifies exact snapshots of the parent
READY/build/selection, the binary hashes, completed smoke and bracket queues, whole-host admission,
drain/memory receipts, all native file hashes and exact packet49 output tokens.
Smoke and bracket must share the current boot. No parent code is imported.

All twelve prompts in each of A0/B0/A1/B1/A2 must be exact and uncached. A0 is
reported as warm-up and excluded only from speed and drift. Both p60fusion
views must reach 1.005 times EACH remaining production control; warm-control
max/min drift must be at most 3%. Strict gain is min(B0,B1)/max(A1,A2)-1.
Applied to **29.260**, it must reach **2%** (29.8452 tok/s projected).
This is a launch gate, never a measurement. Missing or failed evidence refuses.

The CPU preparation marker can exist while device qualification is pending.
It explicitly records that distinction. The coordinator must rerun readiness
after the bracket, inside the **same uninterrupted whole-host hold**. Keep both
lanes drained. Use only the environment-embedded command in `ready.json`.
See [WINDOW.md](WINDOW.md) for the exact unit, output and fresh fault-review path.

K1a → K1b → KD → W2m → WS → WS128x → WS128, with unchanged 90-second gaps.
Freeze Codex units and block compiles from WS through completion of WS128.
Only fresh WS128 supplies the record value; WS128x is exactness only.

## CPU checks and submission

Use nice19, cores 8–15/24–31, python3 -B and closed stdin, below 4 GiB RAM.
`run_cpu_gates.py`, `argument_gate.py`, `rehearse_submission.py`, `seal.py`,
`seal.py --verify` and `plan_gate.py` are the preparation checks. Native CPU
proofs are inherited by hash from 58ab; full-shape/model reads are not rerun.
`restore_build.py` restores the five native binaries by hash without compiling.

The shared submission CLI resolves the repository from its actual packet
location (`parents[4]`), fixing 58z's `parents[1]` defect in this copy.
The rehearsal runs the real CLI with repository-relative evidence paths,
without overriding its root. Synthetic artifacts are temporary and removed;
network access is denied. Historical portable evidence retains its original
timings, tokens and fault counts. Identity substitutions exist only in memory.

Submission notes name the pinned predecessor, HC setting, process/GPU fault
counts and the 128-token scope, within 2,000 characters. The strict512 gate and
second fresh timing pass remain false; 512-token prefill and natural completion
remain unmeasured. This preparation performs no external submission.

## Retention

`lineage/template-files.json` identifies the vendored 58z files. `parent-binding.json`
pins 58ab's final outputs read-only; original build/READY and CPU receipts are
copied under `lineage/`. The parent source closure remains in the frozen 58ab
packet, identified by its build receipt. Binaries are ignored and restorable.
The ignored 40 MB historical rehearsal bundle restores from 58w's portable
bundle, SHA-256 `21aef47ba199f201ad84ca63cf8971d4839d25f02257d20343fee906924348e6`.
No original evidence is removed. Existing packets and live queues stay frozen.

[Work note](../../../../notes/2026-10-18-own-runtime-packet58ad.md).
