# Packet58u host admission — CPU closeout

<!-- campaign-closeout -->

## Question and identity

Can the next one-card Flash-Next quantized compressed version packet use a
measured host bound without modifying 58r/58t? October 18, 2026; CPU-only
analysis of 58g/58k/58n/58p, plus 58t's resident lookup design. Target-only,
one B70, 18 GB expert cache, full BF16 KV and unchanged device allowance.

## Outcome

Prepared a sealed, independently copyable policy module. Required available
memory is 95.401 GB, including the unchanged 8 GiB reserve. It admits the
saved 14:58 reading that the old 118.309 GB requirement refused. The module
changes no existing packet, runtime, queue, device state or host setting.
The [CPU test receipt](evidence/cpu-tests.json) is the validation authority.
No speed, output-quality or full-size resident measurement is claimed.

## What worked

Every retained sample is re-accounted and exactness samples are normalized to
the same full-file allowance as timing. Complete native after-load/cache/KV
censuses support the model-window receipts. The maximum plus 4 GiB retains
margin; the live 8 GiB floor, shadow stop and combined stop remain executable.
Resident lookup bytes replace their existing file allowance explicitly, with
the actual copy charged through anonymous memory.

## What failed or remains uncertain

The old full-device host-shadow reservation refused a host with 115.481 GB
available even though accounted peaks were below 82.517 GB. This does not
establish a universal upper bound: sample intervals, a different runtime or
driver, and unmeasured resident behavior remain limits. Next-packet launch
integration and all device checks are pending. Frozen seals are not repaired.

## Evidence and patches

[Derivation and pins](measured-peaks.json), [reproducer](derive.py),
[old plan](base-plan.json), [new admission/live sensor](memory_plan.py),
[tests](test_memory_plan.py), [seal](seal.json), [accounting and integration](README.md).
Original receipt trees are retained; the new packet stores small derived
metadata and source hashes, not duplicate model payloads or new GPU output.

## When to revisit

Copy forward at the next new one-card packet, pass its actual argument/window
gates, and let the coordinator admit it. Revise the bound in a new seal when
its identity or allocation footprint changes or new receipts exceed the fit.
Keep the live stops; never lower the reserve merely to pass admission.
