# Packet52 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can deterministic new accumulation orders recover at least 120 us per ordinary
IQ3-lane M1 layer? The packet uses seven actual production class shapes,
accepted packet49c controls, synthetic finite payloads with the real formats,
and five separately named orders. The coordinator's target is B70 card0,
PCI0000:23:00.0. This closeout covers CPU preparation on 2026-10-17 only.

## Outcome

Preparation passed: GNU/Intel host builds, device compile-only build, four
fresh 35-case CPU arithmetic runs and two fresh 42-comparison full-shape M1
host runs. The 15 mocked window/parser tests pass. No GPU timing, device
exactness, model quality or arithmetic-v3 decision is claimed. The E/T gates
remain pending; no candidate is rejected or selected on speed yet.

## What worked

Independent scalar mirrors and full production composition checks caught
harness risks before device windows. Static format/order kernels, scoped
fixture restoration and a bounded five-arm family make the intended window
size explicit. The shared winner rule is verified against both-owner threshold
and incompatible-winner negative tests.

## What failed or remains uncertain

The first Intel host process failed before main on a missing runtime library;
RPATH fixed it and the refusal is retained. Review corrections and limitations
are in [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md). The valid-active finite probe does
not qualify every production error/exception path. Native byte equality,
fresh device repeatability, actual runtime duration and speed remain unknown.
CPU BF16 agreement is not a full-model oracle or an old-order identity claim.

## Evidence and patches

[CPU receipts](cpu-gates.json), [Python gates](python-gates.json),
[build closure](build-receipt.json), [seal](seal.json),
[independent review](REVIEW.md), [retention](RETENTION.md),
[CPU rebuild commands](CPU-BUILD.md), and the
[task note](../../../../notes/2026-10-17-own-runtime-packet52.md).
The original source is retained in this packet; previous sealed packets remain
unchanged. Only this packet's regenerable compiler scratch was removed.

## When to revisit

The coordinator runs [E1/E2/T1/T2](WINDOW.md) after protected work releases the
card. Complete passing receipts decide the registered 120 us rule. If it passes,
freeze one exact class/order map for [arithmetic v3](ARITHMETIC-V3.md) and later
packet53; otherwise record measured class ceilings and a negative closeout.
No oracle is started by this packet.
