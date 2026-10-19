# Packet58as record-chain coordinator contract

**BLOCKED: the unchanged native binary cannot select spin for these record windows.**
Its parser rejects --wait-policy; the bracket interface cannot express KD/W2m or WS.
Both READY markers and ready.json are false. Do not launch this draft.
The command below describes the required interface, not one supported by this binary.
See evidence/chain-native-interface.json for sandboxed parser proof.

CPU preparation only. Recheck seal.py --verify and verify_ready.py --output ready.json.
Use the exact chain_command in ready.json. Unit: packet58-onecard-58as-a.
Fresh output: evidence/card0-58as-a. Fresh fault review:
evidence/fault-review-58as-a.json (fault_review.py immediately before launch).

Pause and drain both lanes. Hold the whole host through
K1a → K1b → KD → W2m → WS → WS128x → WS128, with 90-second gaps.
Freeze Codex from WS through WS128 completion; no compiles or model/full-shape
reads during timing. One attempt, no retry, graceful teardown on every exit.
K1a/K1b/KD use helper cores and nice19; W windows use lane-A cores and nice0,
as in packet58aj. No service restoration or host setting change.

Use the existing packet58as bracket binary, never rebuild. Every model window
uses --wait-policy spin, --wait-seconds 300, resident lookups, BF16 KV at 4096,
21,552,729,600 cache bytes, max cache, overlap maintenance, zero-copy misses,
tile16, p60fusion, HC-wide, wide64+halfcache, other fusion and ordered retirement.
K1 proves exact fixture bytes and zero-copy; all model windows must exactly
match iq3-p49-split32-v1. Preserve memory, fault, drain and storage admission.

The completed v5 bracket is readiness evidence only: 60/60 exact; A0 warm-up
excluded; both spin views beat every warm poll control, minimum +8.58%, drift
0.096%. Owner-thread CPU about 33% spin vs 25% poll, measured as one core.
Bounded spin is a host CPU wait policy (250 us then <=20 us sleeps), not a
setting/governor or arithmetic change. See the packet58aq diagnostic note.

Only fresh WS128 supplies record timing. It must exceed the pinned one-card
31.966819787781944 tok/s (31.966820 displayed), cmveqsmsl00ebrf014yvrsosx,
and the live ledger. Scope is 128 tokens, strict512 false; a second fresh timing
remains pending. Submission preparation is offline; this handoff publishes no
performance claim and performs no network submission.
