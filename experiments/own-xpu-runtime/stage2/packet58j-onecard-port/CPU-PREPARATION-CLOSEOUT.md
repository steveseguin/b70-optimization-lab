# Packet58j CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Port the confirmed target-side down-tile16, route-fast and rec-both-plus
changes into a separate copy of frozen packet58g on October 18, 2026.
The intended device is B70 card 0, all 48 layers, target-only decode,
`iq3-p49-split32-v1`, full BF16 KV and the unchanged 18 GB expert cache.
The [parent](parent58g-source-manifest.json) and
[port](port-source-manifest.json) manifests bind the source inputs.

## Outcome

CPU preparation is complete. Both engine builds, both compiler byte gates,
all extent and admission checks, 109 Python checks and ten plan-only rehearsals
pass. The sealed build is 160,667,337 logical bytes, below the 300 MB cap.
The eight selectable combinations include production.
The proposed device bracket and conditional fresh record chain are described
in [WINDOW.md](WINDOW.md). No device speed or model-output qualification is
claimed by this closeout; no device, service or live queue was launched.

## What worked

The transpose happens in bounded, tile-aligned chunks while pinning weights.
Cache fills copy the transposed bytes; zero-copy misses use the same layout.
The CPU checks compare actual indirect kernel submissions with the original
output for host, copied and mixed expert placements.

All [80 full-size checks](evidence/fullshape-submit-cpu.json) use the real
3,446 allocation rows, both miss paths, all five model windows and eight
views. They exercise 1,486 submission sites at short and full context and
retain the old p28 refusal. [All 56 admission plans](evidence/budget-cpu.json)
equal 58g; the cache and reserves are unchanged. The existing engine builds,
extent, K1 and reset results survived the session interruption and were reused
after checking their hashes.

## What failed or remains uncertain

E1 half-cache would add 616,038,400 pinned bytes, so it is excluded under
the frozen budget. GNU and Intel can propagate different NaN payloads in
the unchanged recurrence reference. Each candidate must still equal its
own compiler's reference in raw bytes and across fresh processes; no NaN
normalization or arithmetic change is permitted.

The resumed review fixed a campaign reporting defect: a losing bracket or
fresh confirmation now returns failure and stores `passed=false`. Mocked
campaign tests exercise both winning and losing outcomes without a device.

Device output parity, fresh-process determinism and one-card speed remain
pending. The inherited 128-token suite does not pass the strict 512-token
promotion gate. No submission scope authorization is inherited from 58g.

## Evidence and patches

- [Build and gate commands](CPU-BUILD.md), [byte comparisons](evidence/byte-gates.json).
- [Python checks](evidence/python-cpu-gates.json), [K1 checks](k1-cpu.json),
  [reset checks](request-reset-cpu.json).
- [Sealed inputs and binaries](build-receipt.json), [retention](RETENTION.md).
- [Ten plan-only rehearsals](evidence/launch-plans.json).
- [Decisions not to repeat](DO-NOT-REPEAT.md).

## When to revisit

The coordinator schedules the card-0 production / port / production bracket
after the two-card record chain in a whole-host gap. A qualifying bracket
admits one fresh record chain in a separate folder. Both must beat both
controls and the saved one-card record under the unchanged exactness gates.
The CPU task does not enqueue or run those device windows.
