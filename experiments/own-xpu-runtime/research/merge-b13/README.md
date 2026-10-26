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
