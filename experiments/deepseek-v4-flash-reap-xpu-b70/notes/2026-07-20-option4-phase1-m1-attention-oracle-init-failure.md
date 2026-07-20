# 2026-07-20 Option 4 Phase 1 M1 attention oracle initialization failure

## Numbers first

- **Verdict: FAIL / STOPPED at Step 1 before capture.** Do not claim a Phase 1
  component or endpoint result.
- Requested packet root:
  `/mnt/fast-ai/deepseek-v4-corpora/m1-attention-boundary-v1-20260720T225919Z`.
  It contains **0 files**, **0/344** required rank/layer/bucket manifests,
  **0/43 layers**, and **0/2 buckets**. There is no packet checksum because no
  packet was created.
- Exact buckets remain unattempted: `SWA-resident` at decode position `64` and
  `compressed+SWA-window-full` at decode position `512`.
- Capture requests: **0**. The TP4 service failed in dummy warmup before the
  HTTP endpoint became ready.
- Component gate: changed input **0/40**; fixed-address replay **0/70**;
  positions 28 and 58 **not run**; per-layer parity **0/43**; eager/V1 boundary
  counts **not measured**.
- Endpoint gate: PIECEWISE nesting **not run**; eager break and host sync count
  **not measured**; control/candidate median ms/token **not measured**; output
  token exactness **not run**. The threshold remains `22.381408 ms/token`
  against the `22.881408 ms/token` baseline.
- Phase 2 FFN/MoE boundary: **NO-GO** because Phase 1 never produced its
  mandatory real-tensor packet.
- Postflight: all four B70 compute devices are free. Logical cards 1-3 returned
  to about `25.89 MiB`; card 0 retained only the desktop allocation.

## Failed gate and exact cause

The bounded eager TP4 oracle loaded the 46 K160 shards and entered vLLM's
sparse-MLA dummy warmup. The new default-off packet adapter then failed at:

```text
vllm/models/deepseek_v4/compressor.py:325
state_cache.view(total_state_slots, -1)
RuntimeError: view size is not compatible with input tensor's size and stride
```

The real compressor state cache is a non-contiguous layer view. The adapter's
capture bookkeeping ran whenever the platform was XPU, even though the arm
file was absent; the recorder itself discarded inactive records, but the
preparatory flatten/gather happened first. This is an adapter bug, not a K160,
oneCCL, attention-arithmetic, or device failure.

The direct repair is to guard all capture-only bookkeeping on an explicit
recorder-active predicate and gather the declared state rows with the real
strides instead of flattening with `view`. Per the run instruction, this was
not patched and retried after the Step 1 failure.

## Preserved identity and evidence

- K160 revision:
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- model manifest SHA-256:
  `08535b4ad7fd94419c7eadb1f6cf7f1de583d64f92a1760c86aa238972904e78`;
- capture vLLM commit:
  `fbbf066d8a58cf069ad657ff888a08fa78a08fbe`, based on the exact native-K2
  seam at `50e6a21116a24853ccae065caeefc843435ded05`;
- XPU source commit:
  `5a1e9fa4602f69302dc50ecf85b06b6f86762117`;
- loaded `_xpu_C.abi3.so` SHA-256:
  `d62ea1cf4728250809052c68fdd74983b4f2c0dcaf924624e7a507c8d4c8392f`;
- oneCCL source `48fda4f0e074db005596d6899d5227d3f0316c12`, loaded binary
  SHA-256 `53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9`;
- run root:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/option4-m1-attention-oracle-20260720T225919Z`;
- server log SHA-256:
  `5453db2bdf38860e7eb88798839f2f6fab9b7891f5df29a3d6041b883d163fd4`;
- identity SHA-256:
  `e50067ada98c9e8037ab09bd5d938881e94b84d45997cc14ce687c5499377397`;
- preserved patch:
  `patches/deepseek-v4-flash-xpu-b70/2026-07-20-option4-m1-attention-oracle-capture-failed-init.patch`.

No XPU shared object was rebuilt. No LocalMaxxing action occurred. No held-out
pack was used for capture, validation, or performance testing.

## Process incident

During a delegated read-only operations audit, one overly broad repository
search surfaced prompt lines from frozen held-out Pack A. The file was not
modified and no content from it was used in this work, but the read violated
the instruction not to open held-out packs. The delegated context was marked
contaminated and excluded from all evaluation work. This incident is recorded
here rather than silently omitted.
