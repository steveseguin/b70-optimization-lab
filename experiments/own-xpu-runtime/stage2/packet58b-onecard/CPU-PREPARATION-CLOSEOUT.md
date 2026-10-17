# Packet 58b copy-queue import repair — CPU closeout

<!-- campaign-closeout -->

## Question and identity

Why did packet58 K1a on card 0 return UR unsupported (44), before any
production expert case? Preserve its one-card IQ3 arithmetic, weights,
BF16 KV, cache and oracle while repairing the smallest native setup delta.
Date: October 17, 2026. All 58b preparation is CPU only.

## Outcome

The regular native command queue passed to `sycl::make_queue` is unsupported
by the installed UR Level Zero v2 adapter. It requires an immediate command
list. Packet58b changes that handle, creation/destruction pair and explicit
in-order flag. It retains the copy-only engine, asynchronous operation,
SYCL properties, explicit lifetime and copy/compute dependency barriers.
Device acceptance and model performance remain pending the same K1-first chain.

## What worked

The changed-path CPU fixture compiles the actual constructor fragments with
a mock of the documented interop contract: parent rejects with 44, 58b passes.
The cache fixture passes 213,816 state checks; the expert fixture passes all
36 cases and 1,522,656 compared bytes against packet49d. No sanitizer campaign.
The existing short Python admission/evidence checks remain part of the seal.

## What failed or remains uncertain

The failed parent run contains no `k1-cases.jsonl`: construction did not return.
It never reached expert allocation or a kernel. The 48.6 GB model allocation
is not involved. The call localization is from program order, the installed
header and adapter diagnostic plus pinned upstream source, not a device trace.
CPU mocks do not establish real native queue import, DMA, host-USM access,
full-model fit, byte parity or speed. Those stay coordinator gates.

## Evidence and patches

- [Exact native change](single_device.cpp) and [parent identity](parent58-source-manifest.json).
- [Pinned Intel source and installed adapter evidence](evidence/root-cause.json).
- [Original failure receipt](evidence/failed-K1a-window.json) and [log](evidence/failed-K1a-native.log).
- [Changed-path CPU check](evidence/copy-queue-cpu.json).
- [Cache/expert check](evidence/cache-cpu-gates.json).
- [Build/gate instructions](CPU-BUILD.md); binary/source receipts are sealed by `seal.py`.

No parent source, failed-window evidence, screen job or packet59 work is edited.
The full parent build receipt is retained as historical evidence only.

## When to revisit

Run [the coordinator queue](WINDOW.md) in a fresh output directory. K1a and
K1b must pass before model loading. If the newly reachable stage fails,
retain its exact error and stage; do not cycle the server or call an
unsupported operation a successful fallback. Allocation changes require
allocation evidence; arithmetic and quality gates stay unchanged.

Final CPU completion: both builds pass; production K1 matches the parent's
exact output hash across all 24 placement checks. The reset check matches
40 retained files, and all 44 wrapper checks pass. Build footprint is
148,319,943 bytes. The original packet58 seal still verifies unchanged.
