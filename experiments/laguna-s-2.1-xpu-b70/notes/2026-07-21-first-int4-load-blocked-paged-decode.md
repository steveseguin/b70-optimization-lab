# Laguna S 2.1 first INT4 TP4+EP4 load: ready, generation blocked

Date: **2026-07-21**

## Numbers first

- **TP4+EP4 load:** reached the ready HTTP state in eager mode with graph
  capture disabled. All four ranks initialized, rank 0 reported **64 local / 256
  global experts**, and quantization auto-detected `compressed-tensors`.
- **VRAM:** vLLM reported **16.92 GiB weights/card**, **8.36-8.37 GiB KV
  cache/card**, **1.70 GiB peak activation/card**, and **0.28-0.29 GiB
  non-Torch/card** under the 0.90 memory budget. `xpu-smi ps` showed the owning
  worker at **26.224-26.228 GiB/card** immediately after ready.
- **Correct TP4+EP4 generation:** **not achieved**. The first greedy coding
  request failed before returning a token because the loaded XPU FlashAttention
  binary lacks paged-decode configuration `16,128,64,false,true,false`.
- **Correctness gates:** **not run / not passed**. The first generation returned
  HTTP 500, so there is no exact-token determinism, coding-sanity, factual, or
  arithmetic result to claim.
- **Nonspeculative baseline:** **not measured**; no tok/s number exists to
  compare with the estimated **420-515 tok/s** bandwidth roofline.
- **DFlash:** **not attempted**, because target-only correctness did not pass.
- **LocalMaxxing:** no held-out pack was accessed and no submission was made.

## Artifact and fixture verification

- All **15/15** INT4 shard SHA-256 values matched their Hugging Face metadata
  ETags. The DFlash `model.safetensors` SHA-256 also matched.
- The index contains **72,961 tensors**, exactly matches all shard headers, and
  declares **71,898,444,992 payload bytes**.
- Config, index, tokenizer JSON, tokenizer config, special-token map, chat
  template, and DFlash config matched their Hugging Face metadata identities.
- The completed top-level files are sound. Old `.incomplete` and zero-byte
  `.lock` files remain only inside the download cache; no downloader was active.
- The checkpoint is not mixed INT4/grouped-INT8 despite the initial task
  wording. It contains **36,096 I32 packed weights** and **36,096 BF16 scales**,
  exactly `47 MoE layers x 256 experts x 3 projections`. These are symmetric
  group-32 INT4 routed experts. The ignored attention, shared-expert, dense
  layer-0, embedding, and LM-head weights are BF16. No grouped-INT8 weight
  tensors are present, so no grouped-INT8 selector claim is valid.
- The tokenizer-integrated four-rank meta fixture passed with vocab 100,352,
  exact Unicode/code round trip, chat-template rendering, TP4, EP4, 64 local
  experts/rank, 12 full-attention layers, 36 sliding-attention layers, and six
  DFlash taps `[1,10,19,29,38,47]`.
- Official transform metadata remained offline: the fixture found **zero
  runtime Hadamard modules**.

Fixture log:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/tp4-meta-tokenizer-fixture-fixedregex-20260721.log
```

## Extension and runtime selection

The launch prepended both prepared source trees to `PYTHONPATH`. This corrected
an editable-install trap where the vLLM-only path selected the older kernel
tree:

- `_C` and `_xpu_C`: Laguna kernel tree at `70ab033bfb794244f751387ecc71f657d21ca556`;
- `_moe_C` and `_vllm_fa2_C`: audited source-compatible ancestor tree at
  `18a44f440ca3ac2006d5ba19cd12ccca0a0c9982`.

The real load logged:

```text
Using CompressedTensorsWNA16MarlinMoEMethod
Using 'XPU' WNA16 MoE backend.
Using MoEPrepareAndFinalizeNoDPEPModular
```

The static installed version string still prints old source suffix `g4a6fd8747`;
the actual launch checkout identity was recorded from Git and is listed below.

## Four-B70 preflight

All four per-device allocation/compute checks returned `ok 2097152.0`. XCCL
ranks 0-3 all passed init, barrier, and FP16 all-reduce with result `4.0` over
the current `eno1` interface.

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/xccl-preflight-20260721.log
```

## Load and exact blocker

The final target-only server reached `Application startup complete` with TP4,
EP4, eager execution, maximum model length 8,192, maximum one sequence, prefix
caching disabled, and all cache/temp storage physically on the external drive.
The first launch attempt stopped before workers because the external `TMPDIR`
path exceeded the Unix-domain-socket limit; the final launch used a short
external-drive symlink pointing to the same Laguna cache directory.

The first real greedy coding request then failed on every rank. The primary
error was:

```text
RuntimeError: Paged decode kernel not compiled for this configuration.

Add this line to your paged_decode config file
(csrc/xpu/attn/kernel_configs/paged_decode_default.conf):

  16,128,64,false,true,false

Then rebuild:
  VLLM_PAGED_DECODE_CONFIG=paged_decode_default.conf pip install .
```

The automatic reference fallback also failed:

```text
RuntimeError: expected self and mask to be on the same device,
but got mask on cpu and self on xpu:<rank>
```

Per the bring-up stop rule, no kernel configuration was changed, no extension
was rebuilt, and no alternate attention backend was forced. The service shut
itself down after the fatal engine error. Postflight `xpu-smi ps` showed only
the diagnostic `xpu-smi` process and no retained model allocation; port 18080
was no longer listening.

Final server log with the complete four-rank trace:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/target-eager-20260721/server-final.log
```

## Source identities

- vLLM prepared base: `11813299ffd318aaa803dbf2638735ef29a9a751`
- vLLM tokenizer/fixture follow-up: `024672b34237cfd0f3f5566bb59871b20fa989b6`
- XPU kernels, unchanged: `70ab033bfb794244f751387ecc71f657d21ca556`
- `_moe_C` / `_vllm_fa2_C` ancestor binary source: `18a44f440ca3ac2006d5ba19cd12ccca0a0c9982`
- main lab repository before this note: `136a0ea24980f6972e4f921e851ec8078c11e33e`

The vLLM follow-up adds a real tokenizer load/round-trip/chat-template gate to
the TP4 fixture and requests Transformers' `fix_mistral_regex=True` repair for
Laguna tokenizer construction. A frontend startup warning about that regex
still appeared in the real-service log, so the remaining construction path
must be localized after the attention blocker; no output-quality claim was
made.

## Next round

1. Add exactly `16,128,64,false,true,false` to the pinned paged-decode build
   configuration and rebuild `_vllm_fa2_C` with the same oneAPI 2025.3 toolchain.
   Independently gate the new binary on all four B70s before another model load.
2. Repair and unit-test the reference fallback so its mask is created/moved on
   the attention tensor's XPU device. This keeps future missing-shape failures
   diagnostic instead of fatal, but it is not a performance substitute for the
   compiled kernel.

Only after target-only greedy correctness passes should the cold nonspeculative
suite run, followed by DFlash at the published first depth of seven proposals
with standard exact rejection and greedy draft sampling.
