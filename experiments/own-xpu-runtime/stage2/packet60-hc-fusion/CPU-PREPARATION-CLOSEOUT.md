# Packet60 HC fusion — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can packet56's target HC use three kernels per side while retaining its exact
arithmetic? The coordinator accepted norm; low plus inject; gate plus mix on
October 17. Target: the separate Flash-Next IQ3 quantized compressed version,
packet56's unchanged target arithmetic and packet49 oracle, TP2 on two B70s.
This preparation used only CPU synthetic data on the four-card host.

## Outcome

CPU preparation is complete and the diagnostic screen seal admits the binary.
Both host/SYCL builds pass. All 878,040 compared bytes agree with production
stage references, and all 96 retained mini target layer fixtures and 24 tokens
agree with packet56. No device ran and no speed or full-model equality is claimed.

## What worked

The target Engine hook captures exactly three commands per HC side, with empty
slots for absorbed followers. It covers all 96 sides in the production plan
and the same serial-row path used by M=1/M=2. BF16 intermediates, reduction
trees, error/scratch bindings, residual ordering, FP32 input invalidation and
layer-end hooks are retained. Draft/controller inputs remain packet56.

## What failed or remains uncertain

Parent object files had been reclaimed, requiring local compilation of their
unchanged inputs. The initial fixture import and JSON-log parsing issues are
fixed; [the task note](NOTE.md) retains their details. The first seal refused
the parent's external build symlink, so exact compiler-input snapshots now
close the seal without weakening its path guard. GPU parity, measured launch
costs and matched A/B speed remain untested. The 25–40 microsecond estimate is
only a planning hypothesis.

## Evidence and patches

- [Source delta](evidence/engine-delta.patch) and [unchanged identities](evidence/source-delta.json).
- [Build receipt](build-device-receipt.json), [commands](engine-commands.json),
  [primitive gate](fixture/receipt.json) and [integrated/target gate](integrated-fixture/receipt.json).
- [Diagnostic seal](screen-seal.json) and [CPU-only plan result](evidence/screen-plan.json).
- [Retention and restoration](RETENTION.md); the ignored build tree remains
  available locally and the input snapshots are tracked.

## When to revisit

The coordinator runs [the exact screen command](WINDOW.md) against a matched
packet56 control after fresh device, memory, storage and journal admission.
The CPU plan used the epoch only as a required parser placeholder; it did not
review a journal or authorize a device window. A promising screen still needs
the full sealed quality/repeat/performance chain before any record submission.
