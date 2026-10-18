# Packet127 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Does moving more target-head rows to rank0 improve packet124's exact bundle7
line? Own runtime, IQ3 quantized compressed model, `iq3-p49-split32-v1`, 24/24
target layers, rank1 draft, fixed prefix 80,128, BF16 KV, two B70 cards. Prepare
46,080 / 81,920 / 122,880 / 46,080 on lane B and a conditional A bracket.
This October 18 task is CPU-only and time-boxed to two hours.

## Outcome

CPU preparation passes. Both compilers pass two fresh exact-byte checks at
all three splits, and the reset negative control still catches the old bug.
All 33 startup windows and six rank memory censuses pass. Six intercepted rank
launches preserve inherited limits; the old finite cap refuses. Seventeen
policy, drain and full mocked-worker tests pass. All four proposal files pass
temporary planning. No device execution or model speed gain is claimed.

## What worked

Selection-bound row extents reuse the original per-row head and argmax kernels;
merge arithmetic is unchanged. One compiled executable supports three views.
Rank0's largest tested arena is 28,406,377,588 bytes, leaving 3,805,877,132 bytes
under the unchanged 30 GiB cap. Rank1 pressure falls as rows move. The copied
worker runs exactly twelve cold requests and derives its canary from the first
response. Both local drain implementations are used at actual imports.

## What failed or remains uncertain

The original historical model favors 46,080; the larger points are tests of a
changed composition, not predicted winners. Packet118 does not time rank0
head work separately. Packet120's 25/23 candidate is slower than its first
control, and its trailing control refused teardown because a previous drain
was incomplete; there is no complete matched bracket. Neither supplies a
measured idle budget. Device micro parity, live residency and new split speed
are pending. Initial source assembly missed a copied prototype dependency;
copying that immutable input fixed the CPU build. No device fault occurred
in this CPU task.

## Evidence and patches

[Work note](../../../../notes/2026-10-18-own-runtime-packet127.md),
[bytes](evidence/cpu-byte-identity.json), [startup](startup103.json),
[census](evidence/full-shape.json), [launch limits](evidence/launch-limits.json),
[tests](evidence/protocol-tests.json), [plans](evidence/queue-plans.json),
[runtime diff](integration.patch), [retention](RETENTION.md).
The native caches are ignored; their hashes and original object paths are
retained. No model weights were read or downloaded here.

## When to revisit

Coordinator-owned device windows can run the two exact micros, then the fixed
B grid. A waits for an exact candidate at least 0.5% above both controls and
confirms that same winner. No candidate is adopted without those receipts.
Further source changes need fresh CPU evidence and new seals. This closes
preparation only; it does not close the optimization lane.
