# Qwen3.8 INT4 determinism-pad TP1 causal screen preregistration

Date: 2026-08-20

Status: **completed; criterion passed**

Result:
[`2026-08-20-int4-detpad-tp1-causal-screen-result.md`](2026-08-20-int4-detpad-tp1-causal-screen-result.md)

## Question

The sealed b936 TP1 F2/G pair loaded `_xpu_C.abi3.so` SHA `8f11e716...`,
which predates the known oneDNN INT4 determinism-pad repair. The structured
extraction prompt enters the measured dirty prefill band (`128 < M < 512`).
Test the repair on the same prompt and sealed compile cache using one composite
runtime; change only `VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=0|1` between arms.

## Fixed identity

- GPU 2, TP1, Qwen3.8 AutoRound INT4, MTP5, FP16, margin-free.
- explicit b936 cache namespace and the verified `02db4496...` sealed tree;
- complete composite stage
  `/home/steve/staged-xpu-commitfix-graphfa-composite-20260820`;
- composite `_xpu_C` SHA `4dd33601...`, graph-safe FA extension SHA
  `33938cdd...`, complete graph manifest SHA `47861e83...`;
- strict package/native resolution under the composite stage;
- native GDN spec decode on, ReplaySSM spec off, persistent scratch on,
  captured GDN core on, DDTREE capture off;
- INT4/INT8 completion barriers and input dependencies on;
- no packet/layer trace or quality request; retain F2's fixed smoke request and
  exact four-prompt diagnostic suite at 512 output tokens, so structured
  extraction keeps the same request-order/history position as F2/G.

The runtime candidate contains zero-init scratch, the INT4 pad, and the
ReplaySSM commit fix. The last fix is inert because ReplaySSM spec is disabled.
The pad-off arms use the same binary with its pad explicitly disabled, so the
pad flag is the only runtime-code variable within this screen.

## Order and stopping rule

Run six fresh server processes in this exact alternating order:

1. `detpad0-a`
2. `detpad1-a`
3. `detpad0-b`
4. `detpad1-b`
5. `detpad0-c`
6. `detpad1-c`

Credit the pad for structured extraction only if all three pad-on token arrays
for that prompt are identical and the three pad-off arms contain at least two
distinct structured-extraction arrays. Record the other three prompts but do
not use their unrelated flips to accept or reject this prefill-pad claim.
Every pad-on log must contain
`VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD reached`; pad-off identity must record
zero and its log must not contain the marker. Every arm must resolve `_xpu_C`
and FA to the composite hashes, directly load b936 plus both AOT artifacts,
emit no compile/save marker, and leave the sealed cache tree unchanged.

Any structured-extraction divergence among pad-on arms is an immediate
negative for the pad claim. If pad-off is 3/3 identical, append exactly
`detpad0-d`, `detpad1-d`, `detpad0-e`, `detpad1-e`. If pad-off is still
identical after five arms, classify the causal screen inconclusive; do not
credit the pad.

## Common launch environment

```bash
BASE_STAGE=/home/steve/src/vllm-xpu-kernels
STAGE=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
MODEL_DIR=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
VALIDATION_MODEL_MANIFEST=/home/steve/llm-optimizations/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
VALIDATION_MODEL_VERIFY_SCRIPT=/home/steve/llm-optimizations/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py
VALIDATION_GRAPH_STAGE_MANIFEST=/home/steve/llm-optimizations/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256
VALIDATION_REQUIRE_XPU_MODULES_UNDER_STAGE=1
VALIDATION_TENSOR_PARALLEL_SIZE=1
VALIDATION_NUM_SPECULATIVE_TOKENS=5
VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0
VALIDATION_GDN_SPEC_PERSISTENT_SCRATCH=1
VALIDATION_GDN_CAPTURE_NATIVE_SPEC=1
VALIDATION_DDTREE_FULL_GRAPH=0
VALIDATION_DDTREE_CAPTURE_GDN_CORE=0
VALIDATION_ONEDNN_INT4_COMPLETION_BARRIER=1
VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY=1
VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE=all_target
VALIDATION_ONEDNN_INT8_COMPLETION_BARRIER=1
VALIDATION_ONEDNN_INT8_INPUT_DEPENDENCY=1
VALIDATION_LM_HEAD_INT8=1
VALIDATION_DETERMINISTIC_GREEDY_MARGIN=0
VALIDATION_DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN=0
VALIDATION_PYTHONHASHSEED=0
VALIDATION_ENABLE_XPU_GRAPH=1
VALIDATION_VLLM_EXTRA_ARGS='--dtype float16'
VALIDATION_VLLM_CACHE_ROOT=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-tp1-seed0-shared-20260820
VALIDATION_COMPILE_CACHE_MANIFEST=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-postrecovery-marginfree-mtp5-tp1-sealed-b936-e-20260820/compile-cache-output-manifest.json
VALIDATION_COMPILATION_CONFIG_OVERRIDE='{"cache_dir":"/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-tp1-seed0-shared-20260820/torch_compile_cache/b936042a67","use_inductor_graph_partition":true,"pass_config":{"fuse_rope_kvcache_cat_mla":false},"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[6],"max_cudagraph_capture_size":6}'
VALIDATION_SUITE_OVERRIDE=/home/steve/llm-optimizations/repro/qwen38-27b-autoround-int4-b70/tp1-divergence-suite-v1.json
VALIDATION_RUN_SMOKE=1
VALIDATION_RUN_BENCH=1
VALIDATION_RUN_QUALITY=0
VALIDATION_BENCH_MAX_TOKENS=512
VALIDATION_BENCH_METRIC_TOKENS=100
VALIDATION_ENABLE_PACKET_TRACE=0
VALIDATION_ENABLE_LAYER_TRACE=0
```

For each arm, add `VALIDATION_ONEDNN_INT4_DETERMINISM_PAD=0|1` and invoke
`run-arm.sh spec-native-partition-exact-native 2 ARM_ROOT TARGET_A_QUALITY`.
