# Flash-Next TP1 MTP0 active-0 static-fit closure

Date: 2026-08-28

## Decision

Close only the current-runtime TP1/EP1, eager, MTP0, active-context-0, text
cell as a Grade-D static-fit boundary. This is not a model boot, performance
estimate, quality result, or deployment result, and it changes no captured
speed.

The deterministic classifier validated all 152,089 tensors in all 131
safetensors shard headers against the checkpoint index without reading tensor
payloads. The complete checkpoint is 185,502,232,570 bytes. Text-only MTP0
excludes 897,862,112 bytes (0.836199 GiB) under `--language-model-only` and
2,698,026,496 bytes (2.512733 GiB) under the target loader's `mtp.*` skip,
leaving an exact stored target of 181,906,343,962 bytes (169.413485 GiB).

This host exposes 134,918,307,840 bytes (125.652466 GiB) of physical RAM and
one B70 exposes 34,242,297,856 bytes (31.890625 GiB). Their optimistic combined
physical capacity is 157.543091 GiB, already 12,745,738,266 bytes
(11.870394 GiB) short before runtime, cache, workspace, or operating-system
headroom. Even rounding the card upward to 32 GiB leaves an 11.761019-GiB
deficit.

The accepted TP4 placement does not transfer into a fitting TP1 recipe. Its
selectors would place the full PLE n-gram and input embeddings in host memory,
48.868027 GiB at TP1, while leaving 120.545458 GiB of target weights for one
card. The current runtime has RAM-resident UVA and layer-prefetch mechanisms,
but neither supplies missing physical memory and no disk-backed model-weight
path is qualified for this XPU identity.

## Reproduction

```bash
python3 experiments/qwen38-flash-next-fp8-b70/tools/classify-tp1-ep1-mtp0-static-fit.py \
  --model /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 \
  --host-memory-bytes 134918307840 \
  --gpu-memory-bytes 34242297856
```

The committed output is
[`20260828-tp1-ep1-eager-mtp0-active0-static-fit-boundary.json`](../data/20260828-tp1-ep1-eager-mtp0-active0-static-fit-boundary.json).
Reopen this exact cell only after a material memory design exists: at least
192 GiB host RAM with qualified expert offload, or a separately qualified
compression or streaming path. A later design needs a new preregistration and
must preserve every TP4 result and speed under its original identity.
