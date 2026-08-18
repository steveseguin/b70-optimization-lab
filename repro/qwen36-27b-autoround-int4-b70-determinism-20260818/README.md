# Reproduction — Qwen3.6 27B AutoRound INT4, MTP3 on 2x Intel Arc Pro B70

Reproduces the 2026-08-18 determinism/speed measurements: a deterministic
`92.003 tok/s` configuration and a faster but non-reproducing `96.822 tok/s`
configuration, both passing the quality baseline.

Findings and interpretation:
[`../../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md`](../../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md).
Structured evidence with manifest hashes:
[`../../data/qwen36-27b-autoround-int4-determinism-speed-20260818.json`](../../data/qwen36-27b-autoround-int4-determinism-speed-20260818.json).

## 1. Hardware

- 2x Intel Arc Pro B70, 32 GB each, tensor-parallel 2, concurrency 1
- GPU pair passed to the harness as `0,1`

## 2. Host software

| Component | Version |
| --- | --- |
| OS | Ubuntu 24.04.4 LTS |
| Kernel | `7.0.0-28-generic` |
| Compute runtime (`intel-opencl-icd`, `libze-intel-gpu1`) | `26.18.38308.1-0` |
| Level Zero loader (`libze1`, `libze-dev`) | `1.28.2-1~24.04~ppa1` |
| `xpu-smi`, `libxpum1` | `1.3.6-1~24.04~ppa1` |
| `intel-media-va-driver` | `24.1.0+dfsg1-1ubuntu0.2` |

Confirm the driver with `clinfo | grep -E "Device Name|Driver Version"`; both
devices must report `Intel(R) Arc(TM) Pro B70 Graphics` at `26.18.38308.1`.

## 3. Python environment

Virtualenv `/home/steve/.venvs/deepseek-v4-xpu`, Python `3.12.13`:

| Package | Version |
| --- | --- |
| `torch` | `2.12.0+xpu` |
| `torchvision` | `0.27.0+xpu` |
| `torchaudio` | `2.11.0+xpu` |
| `oneccl` / `oneccl-devel` | `2021.17.2` |
| `intel-sycl-rt`, `intel-cmplr-lib-rt`, `intel-openmp` | `2025.3.2` |
| `intel-pti` | `0.16.0` |
| `numpy` | `2.3.5` |

## 4. Pinned sources

The harness refuses to run unless these match exactly, with a clean working
tree (`git diff --binary | sha256sum` must equal
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, the hash of
empty input).

| Tree | Commit |
| --- | --- |
| `~/src/vllm` | `95a76ff89173ff56e90a2ed384fde2cea3c015e6` |
| `~/src/vllm-xpu-kernels` | `2dd55f380df753a10a88fcd9e96192561066e713` |
| oneCCL source top | `b52f40c07f0b140e6aba87548c80720a350a9827` |
| oneCCL `libccl` | `4ceafd15c03ce46f11eeaf91781a92afebd3cecf` |

oneCCL runtime is loaded from
`/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0`.

> **Trap.** Syncing `vllm-xpu-kernels` with upstream moves `HEAD` and disarms
> every arm with exit code 3 (`kernels source mismatch`). A source sync does not
> rebuild the `.so` files, so during validation the honest state is a detached
> checkout of the pinned commit:
> `git -C ~/src/vllm-xpu-kernels checkout 2dd55f380df753a10a88fcd9e96192561066e713`.
> Your own branches keep the merge.

## 5. Model

`webhie/Qwen3.6-27B-int4-AutoRound`, revision
`f5750c90b3776db658594df5fe8051098226dd8e`, resolved locally at
`/mnt/usb-models/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`.

Quantization: AutoRound INT4 W4A16 target, FP16 target compute, runtime INT8
target LM head with BF16 scales, runtime INT4 group-128 draft LM head.

## 6. Staged graph-safe FlashAttention

Spec arms load `experiments/qwen27_graphsafe_flash_attention/staged-package`,
verified by the harness against these hashes:

| File | SHA256 |
| --- | --- |
| `_vllm_fa2_C.abi3.so` | `33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739` |
| `libattn_kernels_xe_2.so` | `604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c` |
| `libattn_stock.so` | `3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289` |
| `flash_attn_interface.py` | `869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480` |

Give the non-speculative reference the same package with
`VALIDATION_USE_STAGED_XPU_KERNELS_FOR_TARGET=1`; otherwise the two arms run
different attention binaries.

## 7. Commands

Common preamble:

```bash
repo=/home/steve/llm-optimizations
suitebase=/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70
baseline="$repo/data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-repeat64-ctx1024-20260706T140317Z.json"
arm="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
```

Omit `VALIDATION_SUITE_OVERRIDE` so the harness builds the default 25-prompt
suite. Every arm needs a fresh `$root` (it refuses to overwrite) and its own
`VALIDATION_VLLM_CACHE_ROOT`.

### 7a. Deterministic configuration — `92.003 tok/s`, 25/25 self-reproducing

```bash
LABEL=repro-deterministic-mtp3-a
root=$suitebase/$LABEL
VALIDATION_VLLM_CACHE_ROOT=/mnt/usb-models/llm-runtime/vllm-cache/$LABEL \
VALIDATION_RUN_SMOKE=1 VALIDATION_RUN_BENCH=1 VALIDATION_RUN_QUALITY=1 \
VALIDATION_BENCH_MAX_TOKENS=512 VALIDATION_BENCH_METRIC_TOKENS=100 \
VALIDATION_ENABLE_XPU_GRAPH=1 VALIDATION_BATCH_INVARIANT=1 \
VALIDATION_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=1 \
VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1 \
VALIDATION_GDN_CAPTURE_NATIVE_SPEC=1 VALIDATION_GDN_NATIVE_SPEC_COMPLETION_BARRIER=0 \
VALIDATION_ONEDNN_INT4_COMPLETION_BARRIER=1 VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY=1 \
VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE=all_target \
VALIDATION_ONEDNN_INT8_COMPLETION_BARRIER=1 VALIDATION_ONEDNN_INT8_INPUT_DEPENDENCY=1 \
VALIDATION_LM_HEAD_INT8=1 VALIDATION_DETERMINISTIC_GREEDY_MARGIN=0.03125 \
VALIDATION_VLLM_EXTRA_ARGS='--dtype float16' \
LABEL=$LABEL "$arm" spec-native-partition-exact-native 0,1 "$root" "$baseline"
```

All four flag families are required together. Removing any one drops
self-determinism to 9–16 of 25.

### 7b. Fastest configuration — `96.822 tok/s`, **not** reproducible

Same as 7a with `VALIDATION_DETERMINISTIC_GREEDY_MARGIN`,
`VALIDATION_BATCH_INVARIANT`, and
`VALIDATION_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT` removed. Do not promote this as
a record; it reproduces itself on only 15 of 25 prompts.

### 7c. Shape-pinned reference oracle — `46.147 tok/s`, 24/25 self-consistent

```bash
LABEL=repro-reference-a
root=$suitebase/$LABEL
VALIDATION_VLLM_CACHE_ROOT=/mnt/usb-models/llm-runtime/vllm-cache/$LABEL \
VALIDATION_RUN_SMOKE=1 VALIDATION_RUN_BENCH=1 VALIDATION_RUN_QUALITY=0 \
VALIDATION_BENCH_MAX_TOKENS=512 VALIDATION_BENCH_METRIC_TOKENS=100 \
VALIDATION_ENABLE_XPU_GRAPH=1 \
VALIDATION_USE_STAGED_XPU_KERNELS_FOR_TARGET=1 \
VALIDATION_COMPILATION_CONFIG_OVERRIDE='{"use_inductor_graph_partition":true,"pass_config":{"fuse_rope_kvcache_cat_mla":false},"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}' \
VALIDATION_BATCH_INVARIANT=1 VALIDATION_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=1 \
VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1 \
VALIDATION_ONEDNN_INT4_COMPLETION_BARRIER=1 VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY=1 \
VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE=all_target \
VALIDATION_ONEDNN_INT8_COMPLETION_BARRIER=1 VALIDATION_ONEDNN_INT8_INPUT_DEPENDENCY=1 \
VALIDATION_LM_HEAD_INT8=1 \
VALIDATION_VLLM_EXTRA_ARGS='--dtype float16' \
LABEL=$LABEL "$arm" nospec-latest-exact-native 0,1 "$root" "$baseline"
```

The `cudagraph_capture_sizes:[4]` override is the whole point — the harness
default for this arm is `max_cudagraph_capture_size:8` at `run-arm.sh:619`,
which lets the batch float across `[1,2,4,8]` and costs 9 prompts of
self-consistency.

### 7d. MTP4 (negative result)

Add `VALIDATION_NUM_SPECULATIVE_TOKENS=4`, move capture to `[5]`, and set
`VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0` — the serial-exact proof
mode is hardcoded to four verifier rows and raises
`exact recurrent proof requires one request with four verifier rows` otherwise.
Result: `93.680 tok/s`, 9/25 self-determinism, position-4 acceptance `0.333`.

## 8. Sealing and comparison

`run-arm.sh` writes `SHA256SUMS.pre-manifest` on exit. Seal an arm with:

```bash
( cd "$root" && find . -type f ! -name SHA256SUMS -print0 \
  | sort -z | xargs -0 sha256sum > SHA256SUMS )
```

Compare two arms on complete token arrays:

```bash
python3 - "$rootA" "$rootB" <<'EOF'
import json, sys
def load(p):
    return {r["prompt_id"]: r["token_ids"]
            for r in json.load(open(f"{p}/data/bench.json"))["rows"]}
A, B = load(sys.argv[1]), load(sys.argv[2])
same = sum(1 for k in A if k in B and A[k] == B[k])
print(f"{same}/{len(A)} token-identical")
EOF
```

## 9. Expected results

| Arm | Preferred 99-interval median | Self-determinism | Quality |
| --- | ---: | --- | --- |
| 7a deterministic MTP3 | `92.003` | 25/25 | pass |
| 7b fastest | `96.822` | 15/25 | pass |
| 7c reference oracle | `46.147` | 24/25 | not run |
| 7d MTP4 | `93.680` | 9/25 | pass |

Every measured row must report `cached_tokens=0`. Quality passes require
`pass_all: true` and `baseline_match_all: true` in `data/quality.json`.

Expect run-to-run median variation of roughly `±1 tok/s`; the `96.822` arm
replicated at `95.758`, and the deterministic arm's token output is stable even
where its median is not.

## 10. What not to expect

A candidate will **not** be token-identical to a differently-configured
reference. Eleven configurations agree 7–16 of 25 across every cross-config
pairing and 24–25 of 25 only when the configuration is identical. Gate on
self-determinism plus the quality baseline instead.
