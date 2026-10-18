# Packet58ah: one-card full-composition record chain

Prepared ahead of packet58ag's bracket. This is a symlink-preserving vendored
copy of packet58ad's seven-window chain, with packet58ag's five finished
binaries copied and checked by SHA-256. No rebuild, device job, queue edit,
service or submission is performed during preparation. Existing packets stay frozen.

Every model window selects HC fusion, HC-wide, wide64+halfcache, other-fusion
and ordered foreground retirement explicitly. The sealed tile16 dispatch
selection remains unchanged (rows4-shared recurrence). Cache allocation and
usage remain 21,552,729,600 bytes, maintenance overlaps, misses use zero-copy,
KV is BF16, context is 4096, and decoding is target-only greedy. Outputs must
match the registered `iq3-p49-split32-v1` CPU oracle exactly.

The pinned ledger's predecessor is **30.395630964654867 tok/s**,
`cmvefq3ep009orf0186k21lba`. This preparation claims no new measured speed.

## Readiness

`verify_ready.py` replays the completed smoke and v5 evidence through a private
copy of packet58ag's reader. Parent READY, build, source snapshots, selection,
CPU proofs and native artifacts are hash-bound in `parent-binding.json`.
Device evidence is hashed before reading and verified again afterwards;
finished queues, windows, native evidence, exact output and current boot must
agree. There are no imports from the running parent packet.

The smoke requires twelve exact 64-token responses. Each bracket view requires
twelve exact uncached 128-token responses. A0 stays reported and exact, but is
excluded from speed and drift. B0 and B1 must each reach 1.005 times both warm
packet58ad-line controls A1 and A2; max/min control drift must be at most 3%.
Strict gain is `min(B0,B1)/max(A1,A2)-1` and must reach 2%. Applied to the
preregistered **30.396** anchor, the boundary is **31.00392 tok/s projected**.
This is a launch gate, never a measurement or a replacement for fresh WS128.

Missing, incomplete, changed or failing parent evidence refuses launch.
`ready_for_device` records the gate at preparation time; the coordinator must
recompute it after v5, even when a saved marker says true. The marker also
separately records whether CPU preparation passed.

## Coordinator handoff

See [WINDOW.md](WINDOW.md). Retain the same uninterrupted whole-host hold as
packet58ag smoke/v5, including both drained lanes and all 90-second gaps.
Run K1a → K1b → KD → W2m → WS → WS128x → WS128, each once. Freeze Codex and
block compiles from WS through WS128 completion. Use the exact environment-
embedded `chain_command` in `ready.json`, unit `packet58-onecard-58ah-a`,
fresh output `evidence/card0-58ah-a`, and a fresh
`evidence/fault-review-58ah-a.json`. No launch is performed by preparation.

## Validation and submission

All preparation uses nice19, helper cores 8–15/24–31, Python `-B`, closed stdin
and less than 4 GiB RAM. Native/model full-shape proofs are inherited by hash,
not rerun. Entry tests intercept native execution; native parser tests never
load weights. The post-load census and offline submission replay require the
262,144-byte device half-decode table in addition to existing cache/KV checks.

The submission CLI resolves the repository from its final packet location,
without overriding the root during rehearsal. `rehearse_submission.py` copies
packet58ad chain-a's portable bundle into private memory and preserves all
original timings, tokens and fault counters. Its chain identity, flags and
half-table allocation substitutions are explicitly synthetic and confined to
that rehearsal. A separate synthetic above-record fixture exercises the real
CLI's local dry-run with temporary artifacts, removed afterwards. Network is
forbidden throughout. No old timing is relabeled as packet58ah evidence.

Notes stay below 2,000 characters and name the pinned predecessor and full
composition. They disclose the 128-token scope, strict512=false, missing second
fresh timing, and unmeasured standard 512-token prefill/natural completion.
Only a future fresh chain can prepare a real submission.

## Retention

`lineage/template-58ad-files.json` records the original template hashes;
older copied lineage remains historical. `lineage/58ag-*` retains the exact
parent receipts and source snapshots. `restore_build.py` restores the five
ignored native binaries from frozen packet58ag, checking every hash without
compiling. Their combined size is 73,442,424 bytes. K1's CPU proof references
the same local fixture binary, avoiding a duplicate. The 58ad rehearsal bundle
is copied in memory to keep the total new files below 100 MB. Original evidence
is never removed. Admission's exact original parent snapshot is retained;
no host setting changes are needed.

[Validation](../../ops/packet58ah-orchestration/validation.json),
[final marker](../../ops/packet58ah-orchestration/READY-FOR-DEVICE.json),
[work note](../../../../notes/2026-10-18-own-runtime-packet58ah.md).
