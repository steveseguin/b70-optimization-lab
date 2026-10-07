#111 encoding safety preparation

Inactive source delta and CPU controls; no runtime build or live source mutation.
`encode_safety.transform_sd` accepts only exact sealed110 `comfy/sd.py`, SHA256
`d1c63b66a6d0cf467ecb084d7ec5fb73d20b0fac43181668124a8ded06aa7604`.
It adds the existing bound native-safety OOM callback in `VAE.encode` after
`raise_non_oom` and before warning, tiled fallback and allocator-cache flushing.
The existing decode hook and successful encode arithmetic remain unchanged.

The transformation itself does not admit an encoding call. A future provider
must verify the actual native controller binding, request/stage identity, fresh
memory admission, shape and residence before entering native conditioning.
Historical unbound behavior remains unchanged; it is not an admitted111 path.
Do not call the inactive helper against a live source tree.

Six CPU tests passed in0.432seconds against the actual source-extracted
`VAE.encode` AST, fake tensors/devices, and the existing safety controller.
They cover successful ordinary/chunked branches, encoding/load OOM, non-OOM,
closed-controller rejection, source drift/double application and unchanged decode.
Independent review found an empty-slice bug in the first unchanged-decode test;
it now selects the real `VAE.decode` with AST line bounds, verifies a nonempty
body with the existing refusal, and compares its exact bytes. A later strengthened
non-OOM no-warning/no-flush assertion passed separately in0.043seconds.
No actual Torch/model/GPU import or request occurred.

The [memory design](../../notes/2026-10-07-continuation111-memory-design.md)
requires unchanged8/8/2/9GiB admission immediately before each conditioning
stage,2GiB/card afterward, no eviction, original encoder cache cleanup and a
durable first-conditioned-result barrier. Source workspace estimates are not
measured peak guarantees. New request authority, provider registration, complete
capture proof, storage admission and reviewed source assembly remain necessary.

Run the bounded encode controls with:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest test_encode_safety
```
