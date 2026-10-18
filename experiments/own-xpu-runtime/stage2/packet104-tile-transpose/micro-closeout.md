# Packet104 nine-arm micro — closeout

<!-- campaign-closeout -->

## Question and identity

Does packet100's tile16 weight-byte transpose help other selected operations?
Packet104 source at `292727c13`, synthetic weights, lane-B physical card 2,
384 packet100b real target-route vectors, 40 alternating pairs per stratum.
Draft expert timings replay target routes; they are not native draft routes.
See the [measured receipt](evidence/micro-B/window.json) and
[qualification](evidence/micro-B/qualification.json).

## Outcome

No arm passed the preregistered <=0.85 kernel-time ratio gate. Seven arms are
closed in [DO-NOT-REPEAT](DO-NOT-REPEAT.md). TARGET gate/up ratios were 0.898048
and 0.892953 with half-cache. The coordinator authorized screening those two
once despite the failed threshold; [the explicit override](screening-override.json)
keeps the original failure unchanged. No model speed or model quality result.

## What worked

Tile16 keeps weight values and arithmetic unchanged. Both TARGET gate/up paths
reduced operator time in the measured diagnostic. Gate/up's larger contribution
motivates screening, but the expected 0.3–0.5% engine improvement is a coordinator
hypothesis, not a measurement.

## What failed or remains uncertain

Draft/shared expert layouts slowed their selected operations. HC and router
also slowed; target shared Q6 improved too little. Device model exactness,
acceptance and performance transfer remain untested in packet104b. The plain
gate arm removes packet97's E1; the half-cache arm retains it. Half-cache means
exact FP32 decoded weight scales, not a lower-precision KV cache.

## Evidence and patches

All nine kernel sources and the original [micro build](evidence/microbench-build.json)
remain. Full samples are retained locally at `evidence/micro-B/samples.jsonl`;
the [retention instructions](RETENTION.md) describe their compressed Git copy.
[The work note](../../../../notes/2026-10-18-own-runtime-packet104.md) records
both the original preregistration and this exception.

## When to revisit

Screen the two named TARGET arms after CPU qualification. Reopen any other
closed arm only for a materially different layout/access mechanism or a new
explicit coordinator decision. No record chain is admitted by this packet.
