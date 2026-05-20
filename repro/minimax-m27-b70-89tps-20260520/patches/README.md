# Patch Snapshots

These patch files were generated from the active local sources that reproduced the 89-class MiniMax result on 2026-05-20.

- `vllm-active-promoted-minimax-89tps-20260520.patch.gz.b64`
  - Apply from the root of a `vllm-project/vllm` checkout at commit `c51df43005726a09c6eb7348e8c1b00501c70a8e`.
- `llm-scaler-active-promoted-minimax-89tps-20260520.patch.gz.b64`
  - Apply from the `vllm/custom-esimd-kernels-vllm` subdirectory of the llm-scaler checkout at commit `4bfc0070090cc54afdb2d46b8e57882359141568`.

The patches are intentionally broad active snapshots rather than a polished upstream patch series. They are meant to let another machine reproduce this benchmark path first. Upstreamable cleanup should be done separately after reproducing quality and speed.

Decode manually with:

```bash
base64 -d vllm-active-promoted-minimax-89tps-20260520.patch.gz.b64 | gzip -dc > /tmp/vllm.patch
base64 -d llm-scaler-active-promoted-minimax-89tps-20260520.patch.gz.b64 | gzip -dc > /tmp/llm-scaler.patch
```
