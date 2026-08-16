# SergioB Qwen3.8-27B GPTQ INT4 + native MTP on one B70

> **Community-reported, not reproduced here.** Read [STATUS.md](STATUS.md)
> before using this material. The source explicitly labels its measurements
> provisional and pending independent reproduction.

## Why this is interesting

This is a different engine and quality class from the lab's current
two-B70, target-only GGUF Q4_K_M record. It proposes a single-card vLLM XPU
route using a GPTQ INT4 target, a preserved unquantized MTP layer, FP8 KV,
XPU graphs, and four target-verified speculative tokens. The contributor
reports **32.9 tok/s target-only** and **83.7 tok/s with MTP4** at p512/g128.

The portable ideas are:

1. Use the B70's vLLM `XPUwNa16LinearKernel` path with symmetric GPTQ INT4,
   group size 128, `desc_act=false`, and an unquantized MTP exclusion.
2. Keep the draft layer outside the target's GPTQ quantization config.
3. Enable XPU graph capture and use `--max-num-batched-tokens 8192`.
4. Use FP8 KV to make the reported 131,072-token context fit.
5. Reduce `--gpu-memory-utilization` from 0.90 to 0.88 for MTP4 draft
   buffers.
6. Disable prefix caching for the reported cold benchmark identity.
7. Handle an incomplete final speculative group at the exact context
   boundary instead of padding past the configured sequence length.

These ideas are captured for later controlled testing. They do not transfer
mechanically into llama.cpp's GGUF TP2 kernel path.

## Exact reported identity

- Source recipe:
  <https://github.com/SergiioB/intel-arc-pro-b70-inference-cookbook/blob/3beb704b5b86baed2a874a8cc96821116c97e080/docs/qwen38-27/QWEN38-VLLM-XPU.md>
- Cookbook repository:
  <https://github.com/SergiioB/intel-arc-pro-b70-inference-cookbook>
- Model:
  <https://huggingface.co/SergiioB/Qwen3.8-27B-GPTQ-Int4-sym-G128-MTP-BF16/tree/9d189a60e4c0ad7f9f47cd94bfa393ca10b3924e>
- Base model: `Qwen/Qwen3.8-27B`
- Container:
  `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`
- vLLM: `0.27.2rc1.dev77+gac7509e2b`
- vLLM XPU kernels: `0.1.12.3`
- Target quantization: GPTQ INT4, symmetric, G128, `desc_act=false`,
  int32 packing
- MTP: one preserved unquantized layer, reported as BF16; MTP depths 1, 2,
  and 4
- KV: FP8
- Hardware: one Intel Arc Pro B70, 32 GiB
- Benchmark: C1 client post-first decode, cold/cache-off, p512/g128, median
  n=5

The five published weight LFS object hashes and sizes are preserved in
[`reported/source-manifest.json`](reported/source-manifest.json). They total
19,559,450,216 bytes (18.216 GiB), excluding tokenizer and small metadata.

## Contributor-reported results

| Mode | p512/g128 decode | p8192/g128 decode | p130944/g128 | MTP acceptance at p512/g128 |
| --- | ---: | ---: | ---: | ---: |
| no-spec | 32.9 | 31.5 | 23.2 | n/a |
| MTP1 | 52.0 | 50.0 | 38.9 | 100.0% |
| MTP2 | 65.8 | 62.9 | 44.4 | 99.3% |
| MTP4 | **83.7** | **77.1** | **56.3** | 95.0% |

The source reports p8192/g1 cold input at 1774 tok/s without speculation and
1728 tok/s with MTP4. It also calls out one corrupted SSE repetition in the
MTP4 p8192/g32 cell; the reported median was unaffected. Its LocalMaxxing row
is `cmsur82fz06svms01ga1f0z83`, but the source still labels the evidence E2,
self-reported, provisional, and not for a public headline.

## Review findings and open questions

### 1. The published patch checksum is inconsistent

The recipe says `patch_mtp_nightly.py` has SHA-256 `f1db50bf...`. The file at
the pinned cookbook commit, at the first Qwen3.8 recipe commit, and throughout
its public Git history hashes to:

```text
4d7a02c4ea10ca7c00dc89ad927fa3dafa747dbf0553d2adf24e30a3c53e9c14
```

The cookbook's `FULL-SETUP-COMMANDS.md` and older result summaries also use
`4d7a...`. The copied file is the repository version and the manifest records
both values. A reproduction must not claim byte identity with the documented
`f1db...` artifact unless that missing blob is obtained separately.

### 2. The MTP build patch appears redundant for the pinned model

The patch says it is needed because the checkpoint has `dynamic=null`.
However, both `config.json` and `quantize_config.json` at the exact pinned
model revision contain:

```json
"dynamic": { "-:.*mtp.*": {} }
```

The unmodified vLLM anchor embedded in the patch already detects a dynamic key
that begins with `-:` and contains `mtp`, then clears the target quantization
config while constructing the draft. Therefore the env-gated patch should be
unnecessary for the published artifact. This needs an isolated container A/B:
verify selected linear kernels and output parity with and without the patch.

### 3. Draft precision needs direct verification

The recipe calls the 15 excluded `mtp.*` tensors BF16, while the model config
declares `dtype: float16` and the server is launched with `--dtype float16`.
The LFS pointer metadata cannot establish tensor dtypes without inspecting the
actual safetensors headers. Before classifying the quality/precision lane,
record the dtype of all 15 `mtp.*` tensors and the runtime draft dtype.

### 4. No raw evidence is present in the public cookbook snapshot

The recipe points to a contributor-local raw result directory. The public
repository contains the summary/submission but not that raw Qwen3.8 run tree.
Consequently the published medians, cache counters, acceptance, token timing,
and quality cannot be independently recomputed from this snapshot.

### 5. Power settings are not portable defaults

The source used a configured 230 W cap and reports transient interval averages
above it. It also reports 3400 MHz actual frequency against 2400 MHz requested.
Do not copy its hard-coded hwmon path or write a cap on this host. Resolve each
card's BDF/hwmon identity, inspect ASRock limits and current policy, and run a
matched safe power A/B only after the software lane is stable.

## Safest future test order

1. Pull the pinned container by digest and inspect package/kernel identities.
2. Download the exact model revision and verify all LFS hashes plus MTP tensor
   dtypes.
3. Start at 150 W, one GPU, 8K context, target-only, prefix cache off, and a
   strict host-memory cgroup. This 15 GiB host previously saw Level Zero
   device-lost/out-of-resource errors in another vLLM Qwen3.8 lane.
4. Gate basic semantics and exact greedy output against a trusted target
   implementation.
5. A/B the nightly patch off/on. It is expected to be redundant for this
   exact model; confirm instead of assuming.
6. Add MTP1, then MTP2, then MTP4, checking accepted tokens, exact target
   verification, output quality, and memory at every depth.
7. Test XPU graphs off/on and scheduler 2048/4096/8192. Keep the first stable
   configuration as the baseline.
8. Test 32K, then 64K, then 131K context. Apply the boundary patch only for
   the exact final-group case it addresses.
9. Only after quality and stability pass, perform a separately identified
   150 W versus higher-cap performance study.

## Preserved files

- `reported/patch_mtp_nightly.py`: current cookbook patch, verbatim.
- `reported/patch_mtp_boundary.py`: current cookbook patch, verbatim.
- `reported/runtime-config.env`: inert capture of model, image, environment,
  and launch flags; no power write and no auto-launch.
- `reported/vllm-qwen38-mtp4-gptq-int4.json`: contributor's LocalMaxxing
  payload, verbatim.
- `reported/source-manifest.json`: immutable source/model/gist identities,
  hashes, claimed results, and audit caveats.
- `reported/LICENSE.upstream`: cookbook MIT license covering the copied code.

The unrelated gist was reviewed at
<https://gist.github.com/burkeholland/f71d1156812fd91e4369308358892817/91d8de389199a7580f49f064f103f48259cc024c>.
It contains no optimization to copy, so its text is not duplicated here.
