# Packet58ab: port the three-stage target HC to the one-card record

CPU preparation started October 18 at 21:50 UTC. Work is bounded to three
hours; the first smoke proposal is due within 90 minutes. No device, service,
live queue or host setting is changed. Existing packets remain frozen.

The source anchor is packet58z's retained 58x source closure, whose archive
SHA256 is `efd357edc751e929553880b2638cada3fedb869d2f8584c51ce9bc2646d3ab9f`.
The current one-card receipt is 29.259764156562692 tok/s, record
`cmvebtu5f009frf01gsnfi2eh`. It is not a new measurement by this work.

Only packet60's target-HC dispatch and three-stage arithmetic are ported.
Final HC and draft are excluded. Tile16, all 48 layers, 21,552,729,600 cache
bytes, overlap, cache policy, BF16 KV, token cap and the packet49
`iq3-p49-split32-v1` oracle remain fixed. The switch is `hc=production|p60fusion`
at a drained boundary within one model load. A0 remains exact and reported,
but is excluded from drift and speed comparison under the packet58wb rule.

The expected 0.8–1.05 ms/token saving is a planning hypothesis from packet147,
not a measurement. A 50% transfer would fail the 2% gate. CPU checks cannot
establish full-model device equality or a speed result.

Initial pull refused unrelated dirty orchestration files; fetch confirmed
HEAD=origin/main at `d7f6c2c2504a158e666a87e86d63c479beff33ae`. Root had
30.73 GB free. CPU work uses nice19, cores 8–15/24–31, python3 -B and closed
stdin; compiler turns use the shared ops gate. No model payload is read.

Milestone 1: private source closure and HC dispatch are implemented; builds
and proofs are in progress. READY is deliberately absent until final checks.
