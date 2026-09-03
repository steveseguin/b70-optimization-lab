# Codex read-only audit: why the --cudagraph-metrics dispatch table never appears on the XPU TP4 line

Date: 2026-09-03 01:40 EDT. Prompt and run by Claude (codex exec -s read-only, gpt-5.6-sol) against overlay head 805cde59. Verbatim output follows.

## Finding

`cudagraph_stats` is never created. The XPU worker selects Model Runner V2, whose graph-dispatch path omits the metric implemented by the legacy runner.

- [`xpu_worker.py:102`](/home/steve/src/vllm-current-main/vllm/v1/worker/xpu_worker.py:102) selects `XPUModelRunnerV2` when `use_v2_model_runner` is true. None of this configuration’s options—MP, EP, compile mode `NONE`, or disabled async scheduling—is a V2 blocker in [`vllm.py:610`](/home/steve/src/vllm-current-main/vllm/config/vllm.py:610).
- [`xpu_model_runner.py:9`](/home/steve/src/vllm-current-main/vllm/v1/worker/xpu_model_runner.py:9) defines `XPUModelRunnerV2` as a thin subclass of `vllm.v1.worker.gpu.model_runner.GPUModelRunner`; it does not inherit the legacy implementation in `gpu_model_runner.py`.
- The startup message `Using V2 Model Runner` at [`xpu_worker.py:102`](/home/steve/src/vllm-current-main/vllm/v1/worker/xpu_worker.py:102) is the direct runtime confirmation.

### First missing point

In V2, [`gpu/model_runner.py:1471`](/home/steve/src/vllm-current-main/vllm/v1/worker/gpu/model_runner.py:1471) obtains `batch_desc`, including the selected `cg_mode` and padded token count. It then executes the FULL graph explicitly at [`gpu/model_runner.py:1631`](/home/steve/src/vllm-current-main/vllm/v1/worker/gpu/model_runner.py:1631).

Unlike V1, however:

- `ExecuteModelState` is built without a graph-stat field at [`gpu/model_runner.py:1689`](/home/steve/src/vllm-current-main/vllm/v1/worker/gpu/model_runner.py:1689).
- Its definition also lacks that field at [`gpu/model_runner.py:1964`](/home/steve/src/vllm-current-main/vllm/v1/worker/gpu/model_runner.py:1964).
- `sample_tokens()` constructs `ModelRunnerOutput` without `cudagraph_stats=` at [`gpu/model_runner.py:1767`](/home/steve/src/vllm-current-main/vllm/v1/worker/gpu/model_runner.py:1767).

Consequently, the field takes its declared default `None` from [`outputs.py:337`](/home/steve/src/vllm-current-main/vllm/v1/outputs.py:337).

By contrast, V1 creates the statistic in `_determine_batch_execution_and_padding()` at [`gpu_model_runner.py:3811`](/home/steve/src/vllm-current-main/vllm/v1/worker/gpu_model_runner.py:3811), carries it through `ExecuteModelState`, and passes it into `ModelRunnerOutput` near [`gpu_model_runner.py:5108`](/home/steve/src/vllm-current-main/vllm/v1/worker/gpu_model_runner.py:5108). The XPU V2 path never calls that V1 method.

## Ruled-out paths

- **`--no-async-scheduling`:** V2 still returns an internal `AsyncOutput`. [`multiproc_executor.py:904`](/home/steve/src/vllm-current-main/vllm/v1/executor/multiproc_executor.py:904) resolves it with `get_output()`, which returns the same underlying `ModelRunnerOutput`; it does not rebuild or strip fields.
- **TP output selection:** [`multiproc_executor.py:316`](/home/steve/src/vllm-current-main/vllm/v1/executor/multiproc_executor.py:316) requests only `output_rank`, calculated at [`multiproc_executor.py:499`](/home/steve/src/vllm-current-main/vllm/v1/executor/multiproc_executor.py:499). The chosen last-PP/first-TP worker would carry the statistic if V2 supplied one.
- **Worker SHM:** this hop uses pickle, preserving dataclass fields, in `MessageQueue.enqueue/dequeue`; it does not use `MsgpackEncoder`.
- **EngineCore/API msgpack:** [`serial_utils.py:124`](/home/steve/src/vllm-current-main/vllm/v1/serial_utils.py:124) uses msgspec’s native dataclass support. `CUDAGraphStat` does not enter `enc_hook`; the typed `MsgpackDecoder(EngineCoreOutputs)` at [`core_client.py:585`](/home/steve/src/vllm-current-main/vllm/v1/engine/core_client.py:585) reconstructs nested `SchedulerStats`. Nothing replaces the field.
- **Scheduler:** [`scheduler.py:1665`](/home/steve/src/vllm-current-main/vllm/v1/core/sched/scheduler.py:1665) reads the field directly, and [`scheduler.py:2467`](/home/steve/src/vllm-current-main/vllm/v1/core/sched/scheduler.py:2467) attaches it unchanged.
- **API logger:** [`llm_engine.py:103`](/home/steve/src/vllm-current-main/vllm/v1/engine/llm_engine.py:103) constructs `StatLoggerManager` with the same configuration. [`loggers.py:107`](/home/steve/src/vllm-current-main/vllm/v1/metrics/loggers.py:107) enables `CUDAGraphLogging`; [`loggers.py:203`](/home/steve/src/vllm-current-main/vllm/v1/metrics/loggers.py:203) observes only non-`None` values. Aggregated logging delegates to the same `record()` implementation.
- **XPU graph wrapper:** [`xpu_model_runner.py:38`](/home/steve/src/vllm-current-main/vllm/v1/worker/xpu_model_runner.py:38) only aliases CUDA graph APIs to `torch.xpu.XPUGraph`. It neither bypasses V2 dispatch nor rewrites `cg_mode`.
- **Mode string:** not causal. [`cuda_graph.py:63`](/home/steve/src/vllm-current-main/vllm/compilation/cuda_graph.py:63) records every supplied statistic without filtering on `"FULL"`; any observation would make `log()` print the table.

## Minimal source fix

Add the V1-equivalent statistic to V2’s per-execution state:

```diff
+from vllm.compilation.cuda_graph import CUDAGraphStat

         batch_desc, dp_sync = dispatch_cg_and_sync_dp(...)
+        cudagraph_stats = None
+        if not dummy_run and self.observability_config.cudagraph_metrics:
+            cudagraph_stats = CUDAGraphStat(
+                num_unpadded_tokens=num_toks,
+                num_padded_tokens=batch_desc.num_tokens,
+                num_paddings=batch_desc.num_tokens - num_toks,
+                runtime_mode=str(batch_desc.cg_mode),
+            )

         self.execute_model_state = ExecuteModelState(
             ...
+            cudagraph_stats=cudagraph_stats,
         )

         model_runner_output = ModelRunnerOutput(
             ...
+            cudagraph_stats=self.execute_model_state.cudagraph_stats,
         )

 class ExecuteModelState(NamedTuple):
     ...
+    cudagraph_stats: CUDAGraphStat | None
```

Read `cudagraph_stats` into a local before clearing `self.execute_model_state`. `AsyncOutput.get_output()` will then preserve it automatically.

The zero-code workaround is `VLLM_USE_V2_MODEL_RUNNER=0`, which selects the already-instrumented legacy `XPUModelRunner`. No files were changed or runtime tests executed.