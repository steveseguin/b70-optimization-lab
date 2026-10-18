# Packet58w: conditional one-card overlap record chain

Prepared on CPU ahead of packet58v's device bracket. **No device work or
submission was launched.** The record remains 26.22859930943809 tok/s,
`cmvdukc200064rf01lqsql9x8`, read from the pinned ledger during preparation.

The new copy uses packet58p's seven fresh windows:
K1a → K1b → KD → W2m → WS → WS128x → WS128, with 90-second gaps.
It reuses all five packet58v binaries by hash; no compilation is needed.
The fixed selection is tile16 down, route-exp32-rank4, rows4-shared recurrence,
production HC, and `cache_maintenance=overlap`. Misses must be zero-copy;
a K1 result selecting streamed misses refuses the chain.

One B70, target-only greedy decode, 18 GB immutable expert cache, host-pinned
experts, context 4096 and full BF16 KV remain fixed. The oracle remains
`iq3-p49-split32-v1`, verified through `oracle-binding.json` and
`shared_oracle.py`. Its external results link is never flattened into a seal.
The template contains no symlinks; the copy manifest inventories that fact.

## Readiness and coordinator handoff

`verify_ready.py` runs the frozen parent's reader in an isolated CPU process.
It reads the exact locations used by packet58v's runner:

- `../packet58v-async-cache/evidence/card0-async-a/smoke/`
- `../packet58v-async-cache/evidence/card0-async-a/overlap/`

Both queues must finish with clean drain and matching binaries. Native files
are rehashed and every output is compared again with packet49. Smoke must
pass all twelve 64-token requests. The five-view bracket must contain all
twelve exact 128-token requests per view, including A0. The first view (A0)
is the cache warm-up and is excluded only from drift and speed comparison.
Both overlap views (B0, B1) must beat **each remaining serial control (A1, A2)
by at least 0.5%**, with A1/A2 control drift at most 3%.
Boundary comparisons use decimal arithmetic. A saved `ready=true` is
never sufficient; queue startup reruns these checks.

This readiness amendment was made **after packet58v's data and before any
packet58w chain**, under the owner's packet58wb instruction. Each one-card
process starts with an empty immutable device expert cache, so the first view
of a one-load bracket runs cold. Packet58v's A0 was 22.731 tok/s; A1/A2 were
26.053/26.079 and B0/B1 were 28.116/28.153. The old rule refused its 14.7%
control drift. The [packet58t precedent](../../../../notes/2026-10-18-own-runtime-packet58t-result.md)
(15:21–15:35 UTC) had the same cold first control: 21.41 versus 26.13 warm.
That historical loss and all packet58v evidence stay frozen. This bracket
compares warm steady-state execution; its rates are not the record value.
A0 remains reported and must be exact. Every 12 × 128 tokens in all five
views is checked again against packet49. The record value comes only from the
chain's own fresh WS128 window. No smoke, exactness, fault, chain, window or
submission validation gate is otherwise changed.

The fresh output is `evidence/card0-58w-a`; the exact service is
`packet58-onecard-58w-a`. `ready.json` carries the complete command, including
the recorded oneAPI library path. It contains no shell environment expansion.
Only PATH, LD_LIBRARY_PATH and OMP_NUM_THREADS are supplied to Python;
Python's automatic `LC_CTYPE=C.UTF-8` is the only permitted locale addition.
Native children receive the checked card mask through the existing adapter.

The coordinator must pause and drain lane B and hold the host through the
whole chain, including gaps. Every individual window also acquires whole-host
admission. It must create the fresh fault-review capture before invoking the
command. The copied review policy still requires exactly the two known boot
fault lines; a new fault refuses launch. No capture or hold is made by this
preparation. No retries, service restoration, hard kills or power changes.

From the repository root, use nice19, helper cores, `python3 -B` and closed
stdin for all CPU commands:

```bash
P=experiments/own-xpu-runtime/stage2/packet58w-onecard-record
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/verify_ready.py" --output "$P/ready.json" < /dev/null
```

The final coordinator marker is
[READY-FOR-DEVICE.json](../../ops/packet58w-orchestration/READY-FOR-DEVICE.json).
It identifies the committed preparation and the SHA-256 of the exact command.
The amended readiness gate passes the real parent evidence; packet58w's own
chain is still unrun. Readiness is rechecked at launch.

## CPU evidence

- [Actual entry replay](evidence/argument-gate.json): all seven real queue →
  window paths, unit and environment gates, passive topology, host admission,
  driver and native argv. Each queue/window entry rejects wrong units and
  extra environment variables. Native execution is intercepted; coordination,
  historical receipts and journal review are explicit synthetic boundaries.
  Current host snapshots and whether an admission fixture was needed are saved.
- [Full-shape startup](evidence/fullshape-submit-cpu.json) and
  [native parser/oracle consumer](evidence/startup-cpu.json): all five model
  windows, contexts 32/4096, real asynchronous engine wiring and unsupported
  mode refusals. Historical 58p requests exercise the actual host comparison
  consumer; they do not establish overlap device parity.
- [K1 bytes](k1-cpu.json): zero-copy, mixed-source and streamed arithmetic match.
- [Python checks](evidence/python-cpu-gates.json): admission, limits, drain,
  fault boundaries, five-view decisions, exact selection and offline submission.
- [Measured host admission](evidence/budget-cpu.json): the frozen 58u module,
  plus 32 MiB async metadata and 1,179,648 bytes of staging backing. Each model
  window requires 95,435,761,152 bytes MemAvailable; K1 requires 12 GiB.
  The 8 GiB live reserve and 4 GiB shadow bound are unchanged.
- [Drain scanner](evidence/drain-fix.json) and
  [inherited-literal audit](evidence/literal-audit.json).

Reproduce in this order: `restore_build.py`, `native_cpu_gates.py`,
`budget_gate.py`, `drain_cpu_gate.py`, `run_cpu_gates.py`, `argument_gate.py`,
`shared_oracle.py --require-complete`, `literal_audit.py`, `seal.py`,
`seal.py --verify`, `plan_gate.py`, `verify_ready.py`.
The oracle gate receipt is the JSON output of `shared_oracle.py` saved to
`evidence/oracle-gate.json`. All run at nice19 on cores 8–15/24–31.
Full-shape mocks need sparse virtual addresses above 4 GiB; their physical
peak stays below the 4 GiB preparation ceiling. Imported launch code changes
no resource limits; `getrlimit` checks run immediately before native exec.

Root must retain at least 25 GB free, including planned writes. `build/` is
ignored, hash-restorable from 58v and below 300 MB. Never reseal after chain
output exists. Existing packet trees and live queues remain untouched.

## Prepared submission tool

`packet58_submission.py` and `submission_cli.py` copy and adapt packet58s's
offline validator. After the chain, the coordinator can prepare a fresh
`submission/<name>` bundle. It replays every window, token, fixture, ownership
and hash; balances six prompt classes; records process major/minor fault counts
and new GPU fault lines; and emits a bound promotion attestation. Only WS128
is timed. WS128x is whole-host exactness only. A second fresh timing run is
still needed for a speed verdict. `realistic_final_gate.passed=false` and no
strict512 claim are mandatory. Standard 512-token prefill and full natural
completion remain unmeasured.

`record-threshold.json` is an immutable snapshot; the predecessor ID is
validated against `submission-policy.json`. Stale public-check wording comes
from that policy, not the tool. Notes are limited to 2,000 characters. The
shared CLI also checks the current live ledger before any later submission.
Preparation tests use synthetic evidence and forbid network access. No real
payload, public submission or live ledger update is made here.

[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet58w.md).
