# Packet58z: one-card max-cache record chain

CPU preparation of packet58w chain b's seven-window structure, using
packet58x's exact binaries and admitted max cache: **21,552,729,600 bytes**,
tile16, overlap, zero-copy misses, host-pinned experts, BF16 KV and packet49
iq3-p49-split32-v1. No chain was launched.

Pinned predecessor: **28.0429892090105 tok/s**, cmve789qr008vrf01pm678ee8.
This packet has no new measured record. record-threshold.snapshot retains
the raw prepare-time ledger; historical references are not live dependencies.

## Readiness

verify_ready.py reads completed 58x smoke-d/max windows by hash through a
private native-output reader. No mutable parent source or build manifest is
imported/pinned. Every prompt is checked against packet49: 12 ×64 smoke,
12 ×128 per bracket view.

| View | Cache usage | Measured tok/s | Role |
| --- | --- | ---: | --- |
| A0 | 18 GB | 23.109763 | Exact, reported cold-cache warm-up |
| B0 | max | 29.568647 | Candidate |
| A1 | 18 GB | 28.156674 | Warm control |
| B1 | max | 29.363935 | Candidate |
| A2 | 18 GB | 28.199899 | Warm control |

A0 is excluded only from drift/speed. Both max views must beat EACH warm
control by 0.5%; warm max/min drift ≤3%. Strict gain is min(B0,B1)/max(A1,A2)-1,
about 4.13%, and must be ≥2%. Before the chain, that gain is preregistered
as applied to 28.043. This is a readiness projection, **not measured 58z
speed**. No prompt/KV/response reuse. Only fresh WS128 sets a new timing.

## Handoff and CPU checks

[WINDOW.md](WINDOW.md) specifies the whole-host hold, fresh fault capture and
review-29 Codex/compile freeze from WS through WS128. Folder:
evidence/card0-58z-a. Exact unit: packet58-onecard-58z-a.
The command embeds the library path from vendored ops/launch_env.py.

argument_gate.py replays all seven real queue/window paths to intercepted
native exec, with 28 wrong-unit/environment refusals. ops/rehearse_entry.py
checks both native parsers and loader environment in its CPU sandbox.
Its JSONL proposal is **rehearsal only**, not a launch proposal: the actual
chain requires the exact unit above.

Use nice19, cores 8–15/24–31, python3 -B, stdin /dev/null and <4 GB RAM.
New checks: run_cpu_gates.py, argument_gate.py, rehearse_submission.py,
seal.py, seal.py --verify, plan_gate.py, verify_ready.py. restore_build.py
copies only five pinned 58x binaries. Native byte/full-shape/startup proofs
are explicitly inherited from those same binaries, not rerun. No model/GGUF
or full-shape reads were made beside the active one-card window.

Admission and native DRM-unit fix come from 58x. Memory samples are hashed
after graceful drain, matching 58x; oracle completion is hash-bound.
No imported runtime module changes resource limits.

The vendored submission validator checks all seven windows, exact outputs,
fresh ownership, max allocation/usage, native args, process/GPU faults and
the prepare-time predecessor. Notes ≤2,000 characters. The owner-approved
128-token scope remains explicit: strict512 false, no second fresh timing,
512-token prefill/natural completion unmeasured. No submission was made.

[Rehearsal](evidence/submission-rehearsal.json) uses a byte-verified copy of
58w chain-b's portable bundle. Production rejects the old seal/cache. Only
in-memory fixtures substitute capacity/chain identities and its historical
ledger; timings/tokens remain unchanged. No adapted payload is written.
The old speed is never represented as a 58z measurement.

## Retention and restoration

lineage/58x-build-source.tar.gz (~12 MB) retains original source members,
build receipt and native gate receipts needed to audit reused binaries.
This artifact is intentionally retained despite the 1 MiB review threshold.
It is not a new build. Ignored ELF files restore from 58x by exact hash.

The ignored 40 MB lineage/58w-chain-b-rehearsal.json.gz restores through
rehearse_submission.py from the original portable evidence, SHA-256:
21aef47ba199f201ad84ca63cf8971d4839d25f02257d20343fee906924348e6.
Only its small report is committed. The oracle results symlink stays external.

[Work note](../../../../notes/2026-10-18-own-runtime-packet58z.md).
