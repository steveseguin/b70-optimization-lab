# Expert integration and arithmetic identity

Packet49b derives from packet49 at `5cda094d2`, whose early cards01 chain
passed. Packet49 is read-only. The baseline still traces to packet45 SPEED6
`34c62b433`, split23, draft rank1, 4K capacity and 39.422 tok/s.

The decision uses [packet48b's copied production evidence](../packet48b-production/evidence-copy/p48b-a-summary.json):
IQ2_S gate/up and IQ4_NL down passed its two fresh exactness owners and
production-matched timing screen. QKV/Z did not pass the M=1 worthwhile screen;
production-matched M=2 was never measured, so those paths are excluded.
Exceptional IQ3_S expert gates remain on their existing implementation.

The production hook replaces the corresponding packed weight banks during
upload, before they are used, and dispatches those two existing P39 sites to
`p49b_expert_submit.cpp`. It retains their guards, reduction order, BF16
rounding, routing, active/error handling and event ownership. It does not
introduce a new M=2 scheduling scheme: SPEED6 invokes these kernels separately
for each verification row, and both rows now reach the expert hook.

The p48b layout ends each row on a 16-byte boundary. Its padding would add
872,939,520 bytes across the target (47 gate/up layers and 48 down layers),
which exceeds rank1's existing 89,364,320-byte arena headroom. Instead this
packet retains the same within-row plane offsets and rounds the final pitch
to four bytes: IQ2_S K2560 is820 bytes, IQ4_NL K640 is360 bytes. Both equal
the source row sizes; no raw and repacked device bank coexist. Memory-plan
and arena/reserve policies are unchanged.

Every expert weight access uses a scalar 16- or32-bit load; no weight access
requires a16-byte row base. IQ2 pair/half offsets remain divisible by2;
IQ4 code offsets remain divisible by4 and half offsets by2. Activation vector
loads retain their independent16-byte alignment. CPU/device fixtures include
rows1,2,3 and nonzero expert IDs, covering non16-aligned row bases.
The pitch difference means packet48b timing is supporting evidence only;
packet49b must pass its own device exactness and full-model speed windows.

`p49b_expert_fixture.cpp` checks48 cases per fresh process across IQ2 gate/up
and IQ4 down, M=1 and both M=2 rows, valid/invalid/partial routes, inactive
rows, sticky errors and nonfinite/denormal activations. GNU and sanitizer
runs use the original P39 arithmetic oracle. K1a/K1b repeat the same output
byte check on the device. The sparse metadata plan gate checks47 IQ2 sites,
48 down sites and142 replacement banks, with unchanged stored bytes.

The QSA arithmetic sources and checker stay unchanged. The sealed static
binding in `oracle-binding.json` references packet49's existing CPU oracle
unit and build. `shared_oracle.py` verifies those pins, delegates completion
validation to the original job module, and returns completion hashes for each
model-window receipt. No new oracle is generated and no running job is touched.
