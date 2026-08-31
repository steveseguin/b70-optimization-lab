# Qwen3.8 Flash-Next FP8 97-weight HC-up authority census

Date: 2026-08-31
Status: frozen before component execution

## Purpose and boundary

The earlier hot-weight gate sampled only the attention hyperconnection up
weights at layers 0 and 47. Source and A28 profile review show that MTP0 target
decode instead executes 97 sequential `[1,320] x [320,10240]` up projections:
attention and MLP hyperconnections for every one of 48 layers, followed by the
final hyperconnection mixer. The weights total 635,699,200 bytes per provider.

This first phase freezes the unchanged production `F.linear` authority for all
97 slots before any full-bank grouped candidate is executed. It is control
only: the tool imports no grouped extension and records
`candidate_invocations=0`. It uses one B70, does not launch a server or load the
full checkpoint, and requires no reboot. It cannot authorize source
integration, endpoint performance, deployment, or a speed claim.

## Frozen identity and method

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` at the local NVMe path;
- index SHA-256
  `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`;
- config SHA-256
  `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`;
- canonical 97-entry `(slot,name,shard,tensor-sha256)` manifest SHA-256
  `da68ed6ed1fa5dba536bd5881799972c6ce079a55a2ca82e1ec8832520a8a5f7`;
- production order: layer 0 attention, layer 0 MLP, through layer 47
  attention/MLP, then the final mixer; `mtp.*` weights are excluded;
- deterministic unique BF16 input per slot from CPU generator seed `20260831`;
- ten complete `F.linear` sweeps, requiring one finite exact BF16 output hash
  per slot;
- exact one-B70 selector, isolated Python environment, and the same frozen
  loader path used by the grouped component stage;
- control-only tool SHA-256
  `78e61ca6b8f617280a39b8630c519c8c21f6a9da24c0fcb79387932375c1031f`;
- frozen core-helper SHA-256
  `8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0`.

The result records all 97 names, shard names, weight hashes, input hashes, and
authority hashes; model/tool identities; process receipt; and the control-bank
XPU allocation delta. It refuses an existing output and revalidates the source
files and CPU weight bank before an exclusive, temporary-file-plus-link write.

## Exact invocation

The following output must not exist:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-round-robin-authority-seed20260831.json`

```bash
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1
export LD_LIBRARY_PATH=/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/qwen38-flash-next-fp8-b70/tools/census-hc-m1-grouped-gemm-round-robin-authority.py
```

After this census passes, a separately frozen two-process alternating candidate
gate may consume its exact authority manifest. The endpoint candidate remains
deferred until that gate passes and an integration design avoids retaining both
the original and packed 606.25 MiB banks per card in steady state.
