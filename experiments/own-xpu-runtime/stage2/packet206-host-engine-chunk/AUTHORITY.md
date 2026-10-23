# Packet206 host Engine authority

## Question and identity

Does opt-in layer-major chunk2 prefill preserve the existing Engine's state and
output on the fixed four-layer synthetic HOST_ONLY model? The same new binary
runs both resident serial and resident chunk2 modes, with context64, vocabulary16,
GDN layers0/2, QSA layers1/3 and PLE layer1. The exact executable and source closure
are recorded in [the build receipt](evidence/build-compile-only.json) and the
executed plan inside [the proof](evidence/host-proof.json).

## Outcome

The designated run passed: two successful owners completed16 requests each,
13SAVE and3RELEASE each. All13 saved checkpoints match between modes, including
all20 state blobs and tokens.bin. The108 candidate prefill endpoints (100 chunk
endpoints and8 serial tails) match the unchanged serial Engine at the same
published positions. Ten parser refusals occurred before owner output creation.
A third owner intentionally failed after layer0/row0, preserved its original
error, published no successful request/checkpoint/chunk trace, and drained safely.
No SIGTERM or retry was needed in any of these cases.

## What worked

The fixture covers fresh requests, interleaved A/B, same-generation resume,
append/repeat/fresh equivalence, odd tails, a one-token prompt, a33-token prompt,
and a61-token prompt near the context64 limit. The boundary seed saves31 processed
tokens plus a pending token. Append consumes that pending token at position31
using the original serial step, grows the context extent to64, and then resumes
chunking. Final prompt and decode timing records retain their original token
positions, input tokens and generated indices; these are execution records, not
performance comparisons.

The first eight generated sequences and six saved checkpoint payloads also match
the retained packet198 host fixture. Those historical bytes are a separate
regression oracle: packet198 used layer-streaming memory mode, while both new
owners use resident mode. Their execution identities differ. No packet198
checkpoint is restored into the new binary, and manifest identity fields are
not rewritten to force equality. New checkpoints explicitly carry
`experimental-host-prefill-chunk` / `v1.2+p206` and their actual binary hash.

## What failed or remains uncertain

The intentional partial-chunk failure is expected negative evidence, not a
successful request. Its outer receipt is failed/exit1 while its healthy underlying
mock owner can drain with teardown exit0; these distinct statuses are retained.

This is synthetic CPU execution with real Engine allocation/capture/operator/copy
paths and simulated Host/LifetimeMock/MockDevice event semantics. It does not
qualify a device, full model, asynchronous device dependency ordering, expert
cache cadence, production quantized arithmetic or serving performance. The tiny
pipeline disables `p27.fp32_input`, so defensive FP32 cache resets are not a proof
of production cached-conversion correctness. Generated token sequences alone are
weak for these tiny weights; intermediate and complete state comparisons are
therefore required. Timing values in raw receipts are not speed evidence.

## Evidence and patches

[authority-inputs.json](authority-inputs.json) pins the unchanged source and
historical input authorities. [fixtures.json](fixtures.json) defines the16 rows;
[host_probe.py](host_probe.py) is the exact executed harness. The new
[read-only checks](tests/test_host_authority.py) independently inspect retained
raw observations and bytes without launching the binary.

[raw-host-proof-index.json](evidence/raw-host-proof-index.json) inventories every
one of the1,102 closed output files (12,930,562 logical bytes).
[raw-host-proof.tar.gz](evidence/raw-host-proof.tar.gz) permanently retains those
exact research inputs, observations, all26 checkpoint snapshots, parser refusal
logs and intentional failure evidence in1,129,044 bytes. It contains no compiler
objects, executable, model payload or environment/credential dump. Every member
was read back and compared with both its SHA256 inventory and the preserved
original file. The index and archive are consumed by the read-only authority
checks; originals remain in `build/host-proof-a` and are not pruned.

Git restores the archive/index with the packet. To inspect the archived proof,
verify the archive SHA256 against the index and extract into a fresh disposable
directory using `tar -xzf evidence/raw-host-proof.tar.gz -C /fresh/empty/directory`.
Archive members are relative regular files; the checks also enforce that closed
inventory. Do not extract over an existing run. Rebuilding the executable uses
the separate pinned build closure, not this research archive.

## When to revisit

Advance only after independently checking this complete host proof. A later
production integration must separately establish actual device argument/event
lifetimes, production state extents, cache and conversion semantics, numerical
exactness and measured end-to-end benefit. This packet makes none of those
claims.
