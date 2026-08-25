# Embedded-MTP Q8/q8_0-KV TP1 SYCL-graph exact-depth R1 result

State: **passed seven raw graph cells; negative optimization; quality pending**.

| Active context | Prefill tok/s | Decode tok/s | Prefill graph phase | Decode graph phase |
|---:|---:|---:|---|---|
| 0 | 894.194091 | 19.020734 | capture and replay; no cache full | verified capture and replay |
| 2K | 871.088091 | 17.938989 | mixed partial; cache-8 full | verified capture and replay |
| 4K | 849.455941 | 17.037098 | mixed partial; cache-8 full | verified capture and replay |
| 8K | 810.191617 | 15.466532 | mixed partial; cache-8 full | verified capture and replay |
| 16K | 747.505555 | 12.712723 | mixed partial; cache-8 full | verified capture and replay |
| 24K | 692.952118 | 10.833383 | mixed partial; cache-8 full | verified capture and replay |
| 32K | 644.910941 | 9.475383 | mixed partial; cache-8 full | verified capture and replay |

Every row and phase gate passed. Depth-0 prefill requested/replayed all 24
graphs with eight records and 16 direct hits. At 2K through 32K, prefill
recorded and replayed eight shapes and disclosed the remaining 20/24/32/48/64/80
requests as `cache_full`, so those phases remain mixed partial. Depth-0 decode
requested/replayed 641 with 638 direct hits and three records; every other
decode requested/replayed 641 with 639 direct hits and two records. All
compatibility-rejection, unsupported-device, update, and recreate counters were
zero.

The performance outcome is explicitly negative. Against matching graph-off
measurement `q36-mtpq8-tp1-kv-q8-context`, graph-on lost at all seven depths in
both phases. Mean deltas were **-1.35% prefill** and **-1.52% decode**; per-cell
losses ranged from -0.76% to -2.19% prefill and -0.98% to -1.98% decode. The
faster graph-off values remain protected and preferred.

The structured result checksum-binds every raw artifact and the exact embedded-
MTP model, q8_0 KV selector, source/three-patch chain, graph build, binary,
backend, and 32-library closure. Cleanup passed with no terminal error. This is
useful coverage/mechanism evidence, but quality remains pending and the packet
does not authorize site publication, quality claims, record submission, or any
replacement of protected or featured speeds.
