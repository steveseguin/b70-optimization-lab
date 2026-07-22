# Laguna S 2.1 paged decode fixed; first correctness gate blocked

Date: **2026-07-21** (run crossed `2026-07-22T03:22Z` in UTC)

## Numbers first

- **FIX A:** added `16,128,64,false,true,false`, built with IntelLLVM
  **2025.3.3**, and passed an independent changed-input reference gate on
  **4/4 B70s** before model reload.
- **Kernel source for rebuild:**
  `09960db2dc944d38697d06a69d08b24a63820960`.
- **Deployed binary SHA-256:** `_vllm_fa2_C.abi3.so`
  `e6faed930bbcd7a366cc55281b99e1a8d7016a8db40ab10015d78f72937c8e64`;
  `libattn_kernels_xe_2.so`
  `9628c4279348c8ad991ed3848a27d296d56b837b8e9455a30745daa1083bde48`.
  The second library contains the generated specialization and must be kept
  with the wrapper.
- **FIX B:** the reference attention mask now follows `attn.device`. The
  explicit CPU-default/XPU-tensor regression passed **1/1** on B70 card 0.
  Final kernel-tree commit:
  `376a269fadb153a1182798d422c3893270b4a04f`.
- **Target-only eager reload:** **PASS / HTTP ready**. Per card vLLM reported
  **16.92 GiB weights**, **8.35-8.37 GiB KV**, **1.70 GiB peak activation**,
  and **0.28-0.29 GiB non-Torch**. `xpu-smi ps` showed the owning worker at
  **27,498,684-27,501,280 KiB/card** immediately before generation.
- **Paged decode crash:** fixed. The request completed with HTTP 200 and did
  not report the old paged-decode tuple.
- **Correctness:** **FAIL** on the first required coding prompt. The response
  was incoherent token-like garbage, so determinism, the remaining coding,
  factual, and arithmetic gates were not run.
- **Further exact missing shape:** every rank reported nonfatal reference
  fallback for chunk-prefill tuple
  `128,true,false,true,false,false`. Per the stop rule, it was recorded and
  not added or rebuilt in this round.
- **Nonspec eager / PIECEWISE:** **not measured / not attempted** after the
  hard correctness failure. No comparison with the `420-515 tok/s` roofline
  is valid.
- **DFlash depth 7:** **not attempted**. No speculative tok/s or accepted-token
  rate exists.
- **Postflight:** service stopped, port `18080` closed, and all four cards
  freed. No LocalMaxxing action or held-out pack access occurred.

## FIX A build and four-card gate

The default paged-decode configuration now contains:

```text
16,128,64,false,true,false
```

The generated header enabled:

```text
is_decode_policy_tuple_enabled<decode_policy_q16_h128_p64,
                               false, true, false>
```

The build used the versioned `/opt/intel/oneapi/compiler/2025.3` compiler,
not the aggregate `setvars.sh` that selects the incompatible 2026 compiler.
Both default attention config files were passed explicitly, and the build
directory was on the Corsair external volume. Build log:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-vllm-fa2-laguna-09960db-20260721.log
```

Build-log SHA-256:
`024dbfa362bc9f82a8c2cb3b914e4465d62e00411a27019387e517c539cbdc6a`.

The reusable gate is
`experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_paged_decode.py`. It masks
one physical card per process, requires exactly one visible XPU, forces a hard
failure if the runtime enters the reference fallback, runs exact Laguna TP4
geometry (`18 Q / 2 KV`, head 128, page 64, window `(511,0)`), changes Q/K/V
and KV length between two cases, and compares against an independent CPU FP32
reference.

| Card | Changed-input result | Worst max abs error | Output SHA-256 prefixes |
| ---: | --- | ---: | --- |
| 0 | PASS | `0.00390625` | `a73755b8...`, `8ed63f75...` |
| 1 | PASS | `0.00390625` | `421cb12c...`, `7e07133d...` |
| 2 | PASS | `0.00390625` | `d64aadb7...`, `92997638...` |
| 3 | PASS | `0.00390625` | `67df0293...`, `d923ef6a...` |

Gate artifacts are:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/paged-decode-gate-card{0,1,2,3}-09960db-20260721.json
```

Their SHA-256 values, in card order, are
`682f1a78...`, `db67f8fe...`, `2a8f1f32...`, and `8e4934ec...`.

## FIX B

The production fallback used `torch.ones(query_len, kv_len)` while the service
default device remained CPU. It now uses:

```python
torch.ones(query_len, kv_len, device=attn.device)
```

The regression deliberately holds the default device on CPU while explicit
paged Q/K/V tensors live on XPU and exercises both local and causal masks:

```text
tests/flash_attn/test_flash_attn_varlen_func.py::test_fallback_masks_follow_attention_device
1 passed in 1.82s
```

## Reload and correctness stop

The reload retained target-only TP4+EP4, eager execution, maximum model length
8,192, maximum one active sequence, prefix caching disabled, and external
cache/temp paths. It reached `Application startup complete` with 64 local / 256
global experts and the XPU compressed-tensors WNA16 MoE path.

The first fresh greedy coding request had `cached_tokens=0` and returned HTTP
200, but its 96-token output began:

```text
onga LiveG
#aseSere_sToaterThe# of0# In#_ in# inA1#F# ...
```

This is a hard coherence failure. The same request emitted the exact missing
chunk-prefill tuple on all ranks:

```text
RuntimeError: Chunk prefill kernel tuple not compiled for this configuration.
128,true,false,true,false,false
```

FIX B kept that fallback operational, but the round does not establish whether
the garbage originates in the reference-prefill path, tokenizer construction,
or another target-path correctness bug. The frontend also repeated the known
`fix_mistral_regex=True` tokenizer warning. Do not infer causality without an
isolated token-ID and compiled-prefill comparison.

Run artifacts:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/target-eager-fixa-20260722T032208Z/server.log
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/target-eager-fixa-20260722T032208Z/first-generation.json
```

SHA-256: server log
`9e0fe4b29a3ae776f3acff5084f7941cac34222ffd532e93faf2d77395a7244d`;
response
`76c0241eeee246c49d33a561ad5a4920dcba1c2706259cb2b089070806f2941a`.

## Ordered next work

1. Add and independently gate only the reported chunk-prefill tuple
   `128,true,false,true,false,false`, then rerun one fresh greedy coding
   response. This removes the repeated reference-prefill path from the
   correctness comparison and is the top target-path blocker.
2. Localize the frontend tokenizer construction that still omits
   `fix_mistral_regex=True`; compare returned token IDs and independent local
   decode before and after the repair. Do not proceed to speed measurement
   until coherent exact-token gates pass.

Only after those checks should the eager cold suite, PIECEWISE target graph,
and DFlash depth-7 lane resume.
