# Packet58v asynchronous cache — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can serial one-card cache maintenance be hidden behind the next position
without changing any model output? Packet58p tile16, Unsloth UD-IQ3_XXS,
`iq3-p49-split32-v1`, one B70/card 0, target-only, 18 GB device expert cache,
48.6 GB pinned experts, full BF16 KV, fixed twelve-prompt oracle. CPU work on
October 18; runtime copy from 58r's one-load v5 and frozen 58j kernel objects.

## Outcome

CPU preparation passes. No GPU, service, live queue, model payload read,
submission or host-setting change was performed. Device exactness, scheduling
and speed remain unmeasured. The 26.228599 one-card record is unchanged.

Current record receipts show 6.991363 ms/token in cache maintenance, not below
the 1.5 ms stop threshold. Fill means are 33.005051 experts and 65.456571 MB.
The 144 pointer publications total 1,179,648 bytes; their separate duration
was not captured. The new implementation therefore proceeds to an unqueued
small smoke proposal, with a larger bracket dependent on that exact smoke.

## What worked

- Separate BCS fill ownership survives foreground event retirement. Shutdown
  and buffer-release checks still account for unfinished fills.
- Two-phase host-pointer revocation and delayed device-pointer publication;
  one transaction per cache, with every observed route updating global LRU.
- One contiguous table upload plus a device scatter. Both arms retain only
  one additional 1,179,648-byte device staging allocation.
- Actual protocol byte/race tests, including delayed completion, in-flight
  readers, mid-position completion and consecutive reuse of the same slot.
- Full-shape native Engine wiring tests exercise all 1,440 projection copies,
  delayed completion and publication. Both contexts 32/4096 bind 1,486 sites.
- CPU K1 zero-copy/mixed/streamed bytes, miniature reset brackets, two parser
  paths, six real Python-to-native argument paths, and 87 policy tests pass.
- Packet58u measured admission plus explicit new allocations, original 8 GiB
  reserve, unchanged device ceiling, drain fix, getrlimit guard and sealed
  shared oracle. Required host MemAvailable: 95,435,761,152 bytes.

## What failed or remains uncertain

The first preparation checks caught duplicate raw/checked header includes,
a post-load census still expecting three allocations instead of four, a
one-view smoke fixture assuming five rows, and validation of the measured
budget before adding its explicit new allowance. These were corrected only
in the new packet and rechecked. There was no device fault.

Victims planned while position t+1 is running cannot be revoked before it
started. This conservative implementation revokes and fills at the following
boundary, adding one position of lag. The lag can reduce hits, and BCS traffic
can compete with zero-copy reads. A separate queue is not proof of actual
hardware overlap. Conditional +6.83%/+8.64% sensitivities assume those costs
away and are not measured wins. Full device smoke remains mandatory.

A one-load repeated bracket is a diagnostic screen. It cannot establish
fresh-process determinism, independent timing repeats or the strict 512-token
final gate. View switches may finish pending cache maintenance; those boundary
costs are not a claim of zero cache traffic or a record metric.

## Evidence and patches

- [Receipt attribution](evidence/measurement.json), [conditional projections](evidence/projections.json).
- [Implementation](async_source.py), [protocol](native/cache_protocol.hpp),
  [publication](native/publish.hpp), [copy provenance](copy-manifest.json).
- [Native build](evidence/build.json), [race/ownership tests](evidence/protocol-gates.json),
  [K1 bytes](evidence/k1-async-cpu.json), [full-shape startup](evidence/fullshape-submit-cpu.json).
- [Launch arguments](evidence/argument-gate.json), [policy checks](evidence/python-cpu-gates.json),
  [oracle binding](evidence/oracle-gate.json), [final seal](build-receipt.json).
- [Temporary queue plans](evidence/queue-plans.json), [reproduction and design](README.md).

Build files are ignored and restored through `restore_fixtures.py` and
`build_engine.py`, using the pinned parent objects. No tracked new artifact
is at least 1 MiB. Frozen parents, all raw receipts and live queues remain.
Hot-expert cache idea: Niko1221 / Strata; implementation is lab-authored.

## When to revisit

Coordinator admission for the whole-host card-0 gap, then the 12 × 64 overlap
smoke. Only its exact matching clean result admits the 12 × 128 five-view
bracket. If either queue dependencies, byte identity or device admission
fails, retain evidence and fix the new copy before further device work.
No launch, retry, promotion or public submission is implied by this closeout.
