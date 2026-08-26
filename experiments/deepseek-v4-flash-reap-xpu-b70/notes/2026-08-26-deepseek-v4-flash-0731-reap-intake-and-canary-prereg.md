# DeepSeek V4 Flash 0731 REAP intake and target canary preregistration

The active candidate is `0xSero/DeepSeek-V4-Flash-0731-REAP` at revision
`ddc04540efda3d2a0788b129f1fad828ddc19b60`. It replaces the older K160
checkpoint only as the active deployment candidate. The historical 80.820052
tok/s result, model identity, draft pack, exact token evidence, and LocalMaxxing
record remain unchanged.

The user-authorized cleanup removed the old hot-copy path and its `current-k160`
link. The immutable historical archive remains at
`/mnt/usb-models/models/deepseek-v4-flash-k160-7c360e1cd4a5168099dbc54d16d929bf6df04990/`;
an old-checkpoint comparison must select that archive explicitly and must not
silently use the absent historical launcher default.

The download is complete by pinned name/size/index inventory and has no local
partial file. Its one-time full hash/header/Hugging Face dry-run gate remains
pending while the Qwen Flash-Next download owns the shared USB I/O path. A GPU
launch is forbidden until that validator emits a passing summary bound to this
exact revision and cached-tree hash.

## Frozen first arm

- four B70s, TP4+EP, DP1, PP1, concurrency one;
- exact record-era vLLM `264c7f2f7`, XPU kernels `313156737`, and oneCCL
  `48fda4f0e` binary identity;
- target-only, eager, graphs off, prefix cache off, FP8 KV, block 256;
- initial configured context 256, followed by a separate 2K arm only after
  readiness and exact canaries;
- native K160 MXFP4 foundation retained;
- every optional target fusion, graph selector, DSpark selector, sharded
  sampler, and old draft pack disabled;
- fresh revision-specific run and compile-cache roots.

The purpose is checkpoint isolation, not a performance claim. It asks whether
the newer target loads and produces a coherent B70 teacher on the exact runtime
foundation. A speed below the old optimized record is expected and cannot lower
or replace any captured value.

## Advancement gates

1. Four-rank preflight, clean exact source identities, full model receipt, and
   readiness pass.
2. Exact arithmetic, copy, factual, and JSON canaries pass with cache zero.
3. A fresh target-only realistic suite establishes the 0731 teacher and its own
   hashes; old-checkpoint hashes are not an oracle.
4. Reapply accepted target-side record optimizations as a separately named
   overlay and require same-checkpoint quality plus matched speed evidence.
5. Build a revision-bound draft-only pack from the new checkpoint's MTP tensors.
   Never pair the old 256-expert draft pack with this 160-expert target.
6. Test DSpark eager first, then PIECEWISE, and only then requalify the accepted
   M7/M8 record overlay.
7. Long-context points are measured independently at exact active lengths; no
   point is inherited, estimated, interpolated, or promoted from the 256-token
   canary.

The intended deliverable is a candidate neural.download package with exact
model/runtime/patch identities, target-only and target-verified-speculation
profiles kept distinct, and all unmeasured context cells explicitly pending.
