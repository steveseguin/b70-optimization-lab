# Packet58as record-chain coordinator contract

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

packet58asd rebuilt own-rt-iq3 once: the chain binary is the bracket binary plus
a process-wide CLI option `--wait-policy poll|spin` (default poll), and nothing
else ([chain-interface.patch](chain-interface.patch), sha256 `57ba0ba08651da94630c7888a3bd435d5e7d3cfde4ecb32c6d5331c187c46b73`).
Chain device own-rt-iq3 sha256 `4f957f34ae11011fa9a2caba6a79e981559e9f9fa0fa3958e20a90460d1b745e`;
bracket device own-rt-iq3 sha256 `83abf236dcfe73bc9da6309fdc1a0c523aab104faa3adcabee3d5589f0b0b1d2`
(kept byte-identical in build/bracket/). Single-view runs select the policy at
the view boundary through the same p58as::wait() the bracket's B views used;
model load keeps the default poll exactly as in the bracket. A supplied policy
that conflicts with a bracket view, or a draft-capture/rank owner, is refused.
K1a/K1b run the unchanged inherited K1 fixture (byte/zero-copy check, poll, no
flag), as in the bracket. Do not rebuild again. Every model window
(KD/W2m/WS/WS128x/WS128) uses --wait-policy spin, --wait-seconds 300, resident lookups, BF16 KV at 4096,
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
