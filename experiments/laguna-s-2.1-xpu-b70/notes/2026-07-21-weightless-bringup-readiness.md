# Laguna S 2.1 weightless XPU bring-up readiness — 2026-07-21

## Result

The Laguna S 2.1 target builds successfully as a TP4/EP4 meta-device module graph on the customized vLLM-XPU tree, and the DFlash draft config/architecture parses with its six target-layer taps. A normalized width-128 Hadamard/FWHT XPU operator was added to the companion kernel tree and tested on one Arc Pro B70 against an explicit NumPy reference. The new tensor-parallel validation permits only block-local transforms whose shard widths align to the configured `head_dim`; global and misaligned transforms remain rejected.

No full checkpoint was loaded. No LocalMaxxing endpoint or held-out pack was used. The protected `llama.cpp` tree was not touched.

## Source trees and commits

### vLLM-XPU

- Tree: `/home/steve/src/deepseek-v4-vllm-xpu-dspark`
- New branch: `experiment/laguna-s-2.1-xpu-bringup-20260721`
- Clean base: `e4af6e380dc1be771a8695720e688ff12af5169d`
- Commits:
  - `11cba3527` — `models: validate Laguna S 2.1 weightless TP4 graph`
  - `11813299ffd318aaa803dbf2638735ef29a9a751` — `quantization: allow block-aligned online transforms with TP`
- Final tree status: clean.

The base was selected because it is the clean tip shared with the prior `option4-decoder` branch and retains the paired custom XPU `expert_map` behavior. The prior branch and all `preserve/*` tags were left unchanged.

No upstream PR was cherry-picked: all required code was already inherited by this base. Provenance checked during bring-up:

| Support | Upstream PR commit | State on selected base |
| --- | --- | --- |
| Laguna target | vLLM #41129, `0899f436aab42f798fb8e728872334c83aaebb79` | implementation present |
| DFlash | vLLM #46853, `4c3c64fcf76450d3d0bbfd3d1725eade0f214710` | exact commit is an ancestor |
| XPU WNA16 MoE | vLLM #41426, `3207e7680e52853db757aeb14489612704687cd6` | implementation present through inherited history |
| XPU compressed-tensors group-32 INT4 | vLLM #45136, `9548a1887fe14e553c5db2c2a76e59fa79fd3ef4` | implementation present through inherited history |
| mixed grouped INT8 loader allowance | vLLM #47154, `c8d2f3cb1485fcca725653fb92a445b6cc10ade7` | exact commit is an ancestor |

The Laguna config adapter was fixed to preserve the checkpoint's separate nested full/sliding attention RoPE configurations through the generic config base class. It now derives the sliding-attention RoPE field used by the model, supplies the checkpoint-compatible defaults, and retains the MoE router soft cap. `tools/laguna_weightless_fixture.py` was added as the repeatable config/module-graph check.

### XPU kernels

- Tree: `/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc`
- New branch: `experiment/laguna-s-2.1-fwht-20260721`
- Clean base: `faacc34d9bda2edbbea227eabca922908d94f0b3`
- Commit: `70ab033bfb794244f751387ecc71f657d21ca556` — `xpu: add normalized H128 Hadamard transform`
- Final tree status: clean.

The kernel registers the existing `_C::hadacore_transform(Tensor! x, bool inplace) -> Tensor` schema for XPU. It uses one 32-lane subgroup per 128-element row, four values per lane, shuffle-xor butterfly stages for widths 1 through 16, register stages for widths 32 and 64, FP32 internal arithmetic, and the normalized `1/sqrt(128)` scale. FP16 and BF16, in-place and out-of-place operation are supported. Other widths are rejected explicitly.

## Weightless TP4/EP4 fixture

Inputs used:

- INT4 config SHA-256: `9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6`
- DFlash config SHA-256: `6195643943c01daa06379a5ee7fce70d9535463bcc02e60733bcd9a9cd2ccda6`

Command:

```bash
source /home/steve/.venvs/deepseek-v4-xpu/bin/activate
export PYTHONPATH=/home/steve/src/deepseek-v4-vllm-xpu-dspark
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
export VLLM_LOGGING_LEVEL=WARNING
python -m torch.distributed.run --standalone --nproc-per-node=4 \
  tools/laguna_weightless_fixture.py \
  --model /media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/int4 \
  --dflash /media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/dflash \
  --tp-size 4
```

Result:

```json
{"device":"meta","dflash":{"layers":6,"target_layer_ids":[1,10,19,29,38,47]},"ep_size":4,"full_layers":12,"layers":48,"local_experts":64,"moe_layers":47,"runtime_hadamard_modules":0,"sliding_layers":36,"status":"PASS","tp_size":4}
```

Every parameter was on the meta device. Assertions covered:

- 48 target layers: layer 0 dense and 47 MoE layers;
- 256 routed experts, top 10, one shared expert, routed scale 2.5, and 64 local physical experts per EP rank;
- per-head gates and a 128-wide head dimension;
- full attention: 48 Q / 8 KV globally, 12 Q / 2 KV per TP4 rank;
- sliding attention: 72 Q / 8 KV globally, 18 Q / 2 KV per TP4 rank, window 512;
- 12 full layers and 36 sliding layers in the checkpoint's one-in-four pattern;
- full-attention YaRN: theta 500,000, factor 32, rotary dimension 64;
- sliding attention: theta 10,000 and rotary dimension 128;
- vocabulary 100,352 and hidden size 3,072;
- compressed-tensors symmetric INT4 weight metadata with group size 32;
- six DFlash layers targeting target layers 1, 10, 19, 29, 38, and 47.

The tokenizer files were not present yet, so this check deliberately used `skip_tokenizer_init=True`. Tokenizer loading remains part of the completed-download preflight.

### Official transform-metadata correction

The downloaded official INT4 config currently declares only offline `weight_input` and `weight_output` Hadamard rotations. vLLM filters transform arguments through `is_online()`, so the official graph correctly instantiated **zero** runtime `HadamardTransform` modules. This implies that the paired checkpoint tensors are expected to contain those weight rotations already.

Consequently, the new XPU runtime H128 op is ready for an online H128 activation-transform configuration but is not selected by this exact official config. It is dormant unless an online transform is configured; no new selector or default was enabled.

## FWHT/Hadamard validation

The mathematical operation is the normalized transform

```text
y = x @ H128.T / sqrt(128)
```

For blockwise `head_dim=128` rotation, the full feature transform is `I_(D/128) tensor-product H128`. A TP shard is independent precisely when its width and boundary are multiples of 128. Laguna TP4 satisfies this for hidden 3,072 -> 768 per rank, full Q 6,144 -> 1,536, sliding Q 9,216 -> 2,304, and 1,024-wide MoE/shared widths -> 256.

The vLLM restriction was therefore replaced with alignment validation:

- TP greater than one is allowed only when `head_dim` is set and the local applicable width is divisible by it;
- global transforms (`head_dim=None`) remain rejected under TP;
- misaligned local widths remain rejected.

Validation results:

- vLLM transform validation: `8 passed`;
- kernel test suite: `14 passed in 1.39s`;
- hardware: physical Arc Pro B70 card 0 only, selected with `ZE_AFFINITY_MASK=0`;
- FP16 and BF16; changing seeded inputs with 1, 7, and 33 rows;
- comparison against an explicit NumPy float64 normalized-Hadamard reference: exact fraction `1.0`, max absolute error `0`, max relative error `0` for every tested dtype/shape after casting to the output dtype;
- in-place alias behavior, involution behavior, empty tensors, invalid-width rejection, and simulated TP4 shard widths all passed;
- the vLLM wrapper resolved the freshly built binary and returned a distinct `xpu:0` BF16 tensor of shape `[1, 128]`.

`xpu-smi ps` showed no remaining test process after completion; the card was freed.

The core extension target itself built and linked successfully with the IntelLLVM/SYCL compiler and headers consistently pinned to oneAPI 2025.3:

```text
/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/build/temp/_C.abi3.so
/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/_C.abi3.so
```

An initial editable `pip install -e .` found no `icpx` through the venv-derived `SYCL_HOME`; retrying after the aggregate `/opt/intel/oneapi/setvars.sh` mixed the 2026 compiler with cached 2025.3 headers and failed in an unrelated grouped-GEMM source at `__DPCPP_SYCL_EXTERNAL_LIBC`. This was corrected for the requested core extension by explicitly reconfiguring the generated CMake tree with the 2025.3 `icx`, `icpx`, SYCL includes, and SYCL library, rebuilding `_C` 19/19, and installing it into the active source package. Its runtime path is `$ORIGIN`, `vllm_xpu_kernels._C` resolves to this Laguna kernel tree, and the installed import is the binary used by the final `14 passed` hardware run and vLLM-wrapper check.

A monolithic rebuild of every pre-existing XPU extension was neither required for this source change nor completed. The extension-origin audit found `_C` and `_xpu_C` resolving from the active Laguna kernel tree. `_moe_C` and `_vllm_fa2_C` resolve from the older `deepseek-v4-xpu-kernels-qnorm-routeportfolio` editable tree at `18a44f440ca3ac2006d5ba19cd12ccca0a0c9982`; that commit is an ancestor of the Laguna kernel branch, and there are no intervening source changes under `csrc/moe`, `csrc/flash_attn`, or `csrc/xpu/attn/attn_interface.cpp`. Those two binaries are therefore source-compatible, but their exact origins must remain in the first-load manifest. Rebuild them with the same pinned 2025.3 environment if a single-tree package is required.

## Download state at handoff

The existing authorized downloads in the prescribed external paths were not modified by this work. At the final check:

- INT4 process still active and approximately 21 GiB allocated; only config/docs files are complete at top level, with shard fragments still under the Hugging Face cache;
- the DFlash process has exited and `model.safetensors` is present at 2,229,962,896 bytes, but a stale 256,000,000-byte `.incomplete` object remains in its Hugging Face cache and must be reconciled before declaring the draft download clean;
- the INT4 tokenizer and completed Safetensors shards/index are not present yet.

Do not start a duplicate download. Preserve and allow the current partial downloads to complete.

## Ordered steps to the first INT4 TP4+EP4 load

1. Let the existing downloads finish in `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/{int4,dflash}`. Confirm there are no `.incomplete` objects or active locks; verify the expected 15 INT4 shards plus the Safetensors index, tokenizer assets, DFlash model files, sizes, and hashes.
2. Verify the installed `vllm_xpu_kernels._C` still resolves to the Laguna kernel tree and exposes `hadacore_transform`. Record every extension origin: the audited ancestor `_moe_C`/`_vllm_fa2_C` binaries are source-compatible, while any newly observed source mismatch must be rebuilt with the pinned oneAPI 2025.3 environment. The Laguna `_C` rebuild/install and its one-B70 test are already complete.
3. Activate `/home/steve/.venvs/deepseek-v4-xpu`, check that vLLM resolves to commit `11813299ffd318aaa803dbf2638735ef29a9a751` and the kernel package resolves to commit `70ab033bfb794244f751387ecc71f657d21ca556`, then rerun the four-rank meta fixture including tokenizer initialization.
4. Inspect the completed Safetensors index and tensor metadata without materializing the model. Classify the checkpoint's mixed INT4 and grouped-INT8 layers, verify group-32 layouts, and confirm the loader selects the intended XPU compressed-tensors dense/MoE paths. Reconfirm that official offline transform metadata still produces zero runtime Hadamard modules.
5. Verify all four B70s are free and healthy, run the existing four-rank XCCL health preflight, and create caches/logs under the external drive or this repository, never `/mnt/fast-ai`.
6. Start the target alone first, with one active generation and conservative eager settings. A first command template is:

   ```bash
   source /home/steve/.venvs/deepseek-v4-xpu/bin/activate
   export PYTHONPATH=/home/steve/src/deepseek-v4-vllm-xpu-dspark
   export ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3
   export ZE_AFFINITY_MASK=0,1,2,3
   export CCL_ATL_TRANSPORT=ofi
   export CCL_TOPO_P2P_ACCESS=1
   export HF_HOME=/media/steve/CorsairExternal/llm-optimization-artifacts/hf-cache
   export VLLM_CACHE_ROOT=/media/steve/CorsairExternal/llm-optimization-artifacts/vllm-cache/laguna-s-2.1
   export TORCHINDUCTOR_CACHE_DIR=/media/steve/CorsairExternal/llm-optimization-artifacts/torchinductor-cache/laguna-s-2.1
   vllm serve /media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/int4 \
     --host 127.0.0.1 --port 18080 \
     --served-model-name laguna-s-2.1-int4 \
     --dtype bfloat16 \
     --tensor-parallel-size 4 \
     --data-parallel-size 1 \
     --pipeline-parallel-size 1 \
     --distributed-executor-backend mp \
     --enable-expert-parallel \
     --all2all-backend allgather_reducescatter \
     --max-model-len 8192 \
     --max-num-batched-tokens 8192 \
     --max-num-seqs 1 \
     --gpu-memory-utilization 0.90 \
     --enforce-eager \
     --no-enable-prefix-caching \
     --generation-config vllm \
     --enable-prompt-tokens-details
   ```

   Let the checkpoint auto-detect `compressed-tensors`; add `--quantization compressed-tensors` only if the completed-checkpoint preflight shows auto-detection did not select it. Capture the exact package commits, environment, tensor-path selections, memory use, and startup log.
7. Run a one-prompt target-only smoke test, followed by fresh exact-token, semantic, arithmetic, and practical correctness gates. Keep cache reuse disabled and verify request/output identity before measuring throughput. Expand context beyond 8,192 only after the basic load and attention patterns are correct.
8. Add DFlash only after target-only correctness passes, using:

   ```text
   --speculative-config '{"method":"dflash","model":"/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/dflash"}'
   ```

   Validate draft loading, all six target-layer taps, target verification, accepted-token accounting, and correctness before any speed claim. Do not use LocalMaxxing until the repository's fixed realistic cold-suite policy gate passes.
