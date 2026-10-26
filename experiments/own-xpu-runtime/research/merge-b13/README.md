# Next service build: three exact lab patches merged (CPU compile check only, 2026-10-26)

`merged.patch` is a unified diff against `engine/src`, which is unchanged since engine 1d72818cfe8c. It combines:

- [decode-experts](../decode-experts/RESULT.md): `OWNRT_EXPERTS_V2=1`.
- [dense-decode](../dense-decode/RESULT.md): `OWNRT_DENSE_DECODE_V2=1`.
- [prefill-experts](../prefill-experts/RESULT.md): `OWNRT_PREFILL_EXPERTS=1`. It raises the prefill row limits to 256;
  the service would need `SC117_PREFILL_ROWS=256`.

The only conflict was one include line in `additive/packed.hpp`, which now carries both includes. The merged tree built
on CPU (binary 67ff0e26f5aa); it has not run on a device.

It is not applied to `engine/src`. Doing that would break the 1d72818cfe8c receipt the owner needs to restore the
service after the card-27 incident (see `../incidents/2026-10-26-card27-bcs-fault/`).

## Deploy order after the restore

1. Apply the patch to `engine/src` and build.
2. One card-27 rank-1 lab run of the merged build:
   - all three switches at 32-row chunks;
   - prompts of 4096 and 300 rows;
   - bitwise against 1d72818cfe8c.
3. Rank-0 memory at 256-row prefill chunks: the plan cap must hold. If it does not, deploy with 128- or 32-row chunks.
4. Service reload with gates and the suite.
5. Add the new env names to `adapter6.py`'s rank environment whitelist.

## Result (2026-10-26, after the owner's restore)

**Lab, card 27, rank 1, merged build.** Every run below was bitwise identical to the 1d72818cfe8c reference on all
1032 buffers (`card27-lab-ab.log`).

| Run | Decode half | 4096-row prompt |
|---|---|---|
| Reference, 1d72818cfe8c | 16.40 ms | 61.9 s (includes kernel compiles on a fresh cache) |
| Decode switches, 32-row chunks | 13.84 ms | 54.8 s |
| All switches, 256-row chunks | 13.86 ms | 17.3 s |

All switches also matched the reference at a 300-row prompt.

**First service start (72693296ae0e) refused.** Rank 0 stopped on "native config prefill trailer". The service-path
native controller still capped prefill chunks at 64 rows, and so did the prefill wire header (`tokens[64]`); the lab
driver does not use either. No GPU fault.

**Fix (5e44953236cc).** `prefill_wire.hpp` sets `max_rows=256` (16 + 1024 bytes, still inside the unchanged 4096-byte
header page), and the controller trailer uses that constant.

**Service on 5e44953236cc (`SC117_PREFILL_ROWS=256`).**
- Gates: F32 oracle at 64K and against the 4096 oracle, zero differences on both ranks; prefill gate 13/13 at 256
  rows; continuation passed.
- Suite: ids, text and MTP hits identical; 49.38 → 56.96 tok/s, faster on 12/12 prompts.
- 10.7K test, ids identical: decode 50.2 → 57.9 tok/s; prompt read 71.2 → 49.1 s.
