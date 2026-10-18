# Packet93: new packed target-head unpack mechanisms

## Diagnosis milestone

Packet74 already removed staging barriers. Its remaining costs include repeated
code-plane loads, repair of alternating two-byte block alignment, runtime scale
conversion and scalar extraction. Production dispatch is p33 WG32, whereas
packet74 used WG256. Register pressure and occupancy are hypotheses until an
offline dump or device evidence measures them. Its retained microbenchmark
receipt is build-only, not measured timing.

[Source diagnosis](../experiments/own-xpu-runtime/stage2/packet93-packed-head2/DIAGNOSIS.md)
preregisters word-parallel extraction and a reversible 210-byte plane layout.
Both keep production FP32 products, additions and SG32 reduction order. The
production expanded path remains the default. Device work is proposed only;
a candidate must take at most 85% of production kernel time in the full-shape
alternating microbenchmark before either screen direction may run.

Preparation is CPU-only on steve-b70s, nice19, cores8-15,24-31, stdin closed,
8 GiB process address-space ceiling, one compiler using the shared turn lock.
Root started at18 GB free; stop below12 GB; packet build limit1 GB. Existing
packets, screen wrappers and live operations are frozen. The required pull
refused unrelated dirty running-chain files; fetch found HEAD=origin/main, so
nothing was stashed or reset. No GPU, service, sudo or host settings changed.

The packed target saves317,849,600 allocated bytes, but the unchanged draft
needs a new308,904,960-byte expanded prefix (production shares its target).
Net rank1 allocation saving is8,944,640 bytes; rank0 is unchanged. Traffic
savings and allocation savings are distinct. All speed estimates are unmeasured.
