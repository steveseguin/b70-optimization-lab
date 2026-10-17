# A367 capture-entry communicator audit (CPU source inspection, 2026-10-17)

Scope: clean source `/home/steve/src/vllm-flashnext-a367-clean-20261016`,
the census command built from the protected `driver/window_driver.py:454-468`,
and census lifecycle hooks. No runtime import, GPU operation, model-weight read,
or device reproduction was performed. File/line references below are relative
to that clean source unless a repository path is explicitly named. This is
source evidence, not a successful device validation.

## Correct rendezvous

Wrap `vllm/v1/worker/gpu/model_runner.py:918`,
`GPUModelRunner.capture_model`, on entry, before its original body.
`vllm/v1/worker/xpu_model_runner.py:30-39` defines `XPUModelRunnerV2` as
its subclass and does not override capture. `xpu_worker.py:143-146`
selects that subclass for V2. Qwen4Exp is a default V2 architecture
(`vllm/config/vllm.py:81-82,646-697,722-740`); the fixed census command
does not override the runner selector. Preserve the pinned V2 identity and
do not silently resume on a legacy runner if selection changes.

Eager-census deliberately disables graphs, so `gpu_worker.py:864` skips the
capture call. Its separate census-only wrapper runs the original
`gpu_worker.Worker.compile_or_warm_up_model` through return (`:827-1005`), then
holds at the same file rendezvous before returning the original CompilationTimes
value. `XPUWorker` inherits this method. Profiling, KV setup and kernel/sampler
warmup (`:941-943`) are complete; engine readiness still awaits the RPC result.
This hook is eager-only; graph-census continues to use capture_model entry.

The engine order is `determine_available_memory` (`v1/engine/core.py:308`),
KV config/allocation (`:319-343`), then `compile_or_warm_up_model` (`:345`).
The worker allocates KV and initializes any configured connector in
`v1/worker/gpu_worker.py:792-813`; compilation/kernel warmup precedes
`self.model_runner.capture_model()` at `:865`. The original capture body
starts target capture at `gpu/model_runner.py:952` and draft capture at
`:966`. Therefore this entry is after normal profile and KV setup and
before either graph capture.

There is another call to `runner.capture_model()` in the graph-memory
profiler (`v1/worker/gpu/cudagraph_utils.py:781`). It is unreachable on
this pinned launch: explicit `--kv-cache-memory-bytes 376569856` takes
the profile-and-return branch at `gpu_worker.py:617-639`; additionally
the alternate graph-memory profiling branch at `:649-660` explicitly
excludes XPU with `current_platform.is_cuda_alike()`. Source pins should
include these call-site and XPU inheritance files, not only the runner.

## Process groups and first use

The fixed command is TP4, PP1, DP1, expert parallel enabled,
allgather/reducescatter backend, MTP1, with default PCP1/DCP1,
no EPLB, no elastic EP, no KV-transfer configuration, and no weight-update
request. `GroupCoordinator` creates device and Gloo process groups at
`vllm/distributed/parallel_state.py:456-465`, then constructs the platform
device communicator only when enabled and world size exceeds one
(`:503-513`). Creating the Python object/process group is distinct from
the lazy oneCCL communicator initialization reported in the failed run.

| Group / path | Membership in this launch | First collective / initialization evidence | After capture-entry risk |
| --- | --- | --- | --- |
| PyTorch default WORLD | ranks 0,1,2,3 | `init_process_group` at `parallel_state.py:1685`; explicit XPU zero-tensor `all_reduce` at `xpu_worker.py:111-118`, before model construction/loading | Already used while paused. |
| vLLM WORLD coordinator | ranks 0,1,2,3, separate group from default WORLD | Created at `parallel_state.py:1722`; device communicator intentionally disabled at `:1303-1311`. CPU node checks use its Gloo group. No normal inference device collective found. Optional distributed weight-loading uses its device group (`model_executor/model_loader/weight_utils.py:1150`), not the configured ordinary safetensors path. | Device group can remain lazy/unused; do not claim it was warmed by the default WORLD collective. No post-rendezvous use found in this launch. |
| TP | ranks 0,1,2,3 | Created at `parallel_state.py:1834-1849`. Initial profile invokes target forward (`gpu/model_runner.py:882-884`); vocab embedding reduction (`model_executor/layers/vocab_parallel_embedding.py:490-517`), model projections and MoE reductions use TP. `XpuCommunicator.all_reduce` calls `dist.all_reduce(..., group=self.device_group)` (`device_communicators/xpu_communicator.py:49-59`). | Target TP communicator exists before rendezvous; graph and request operations reuse it. |
| EP | ranks 0,1,2,3, distinct process group | Created for this MoE at `parallel_state.py:1923-1955`. For DP1/PCP1, `ParallelConfig.use_all2all` and `use_sequence_parallel_moe` are false (`config/parallel.py:710-733`) even though EP is enabled. The applicable final expert reduction uses TP (`model_executor/layers/fused_moe/runner/moe_runner.py:490-496`). | EP XCCL communicator may remain lazy and unused. No EP first collective found after entry for this exact configuration; changing DP/PCP/sequence-parallel settings needs a new audit. |
| DCP | four singleton groups | Created at `parallel_state.py:1851-1867`; world-size-one paths bypass multi-rank communication (`:503`, `:662` onward). | No multi-rank XCCL first collective. DCP > 1 is outside this audit. |
| PCP | four singleton groups | Created at `parallel_state.py:1869-1886`; no PCP parallel execution at size one. | No multi-rank XCCL first collective. PCP > 1 is outside this audit. |
| PP | four singleton groups | Created at `parallel_state.py:1888-1904`; no pipeline traffic at PP1. | No multi-rank XCCL first collective. |
| PP sampled-token broadcast sibling | absent | `gpu/pp_utils.py:85-88` calls `make_sibling_device_group` (`parallel_state.py:535-555`), but `gpu/model_runner.py:315-320` constructs the handler only when PP is enabled. | At PP > 1 its first sampled-token broadcast could be later than profiling; excluded by PP1, not globally safe. |
| DP | four singleton groups | Created at `parallel_state.py:1906-1921`; DP sync is bypassed for DP1. | No multi-rank XCCL first collective. |
| MTP / drafter | shares target TP/EP and existing singleton groups; no separate MTP process group | V2 selects `MTPSpeculator` at `gpu/spec_decode/__init__.py:47-50`. Initial `_dummy_run` invokes `self.speculator.propose(..., dummy_run=True, is_profile=True)` (`gpu/model_runner.py:794-838`); eager draft prefill runs at `gpu/spec_decode/autoregressive/speculator.py:282-316`. MTP1 returns after the first draft step. No `new_group`/group init found in the draft model/speculator subtree. | Draft capture at runner `:966` uses the already exercised group; no separate draft communicator creation identified. |
| Graph-capture-specific groups | none on XPU path | `gpu/cudagraph_utils.py:326` enters `parallel_state.graph_capture`; `parallel_state.py:1474` reuses TP and PP. Coordinator capture (`:619-660`) creates a stream, not a process group. XPU `ca_comm` is `None` (`xpu_communicator.py:29`). | Library-internal stream/operation-specific lazy creation remains unproven by Python source. |
| EPLB / elastic EP / inner-DP-world | absent | EPLB group only when enabled (`parallel_state.py:1963`); elastic/stateless groups and inner-DP-world have separate topology/feature guards (`:1693`, `:1717`, `:1732`). | Runtime reconfiguration/elastic scaling is outside the sealed run. |
| KV transfer | absent | `ensure_kv_transfer_initialized` returns immediately if config is absent (`distributed/kv_transfer/kv_transfer_state.py:81-82`). Its configured initialization would occur during KV setup (`gpu_worker.py:810`), but dummy profile disables the connector (`gpu/model_runner.py:752-778`). | A configured connector could defer network/device work until real requests; do not generalize this audit to KV transfer. |
| Weight-transfer/update groups | absent | `distributed/weight_transfer/nccl_engine.py:149`, `sparse_nccl_engine.py:144`, and `nccl_common.py:53-96` implement update-specific stateless groups. No weight-update operation is in the fixed client. | Dynamic updates excluded; no startup or capture use in this run. |
| Gloo CPU companion groups | each coordinator above | Created with `backend="gloo"` (`parallel_state.py:464-465`); coordinator barriers use CPU group (`:1200-1207`), not XCCL. | CPU coordination does not initialize a Level Zero XCCL communicator. |

## Search coverage and residual risk

The full Python source search covered `new_group`, `init_process_group`,
`create_communicators`, `ProcessGroupXCCL`, `GroupCoordinator`,
`make_sibling_device_group`, and device communicator construction. Direct
Python process-group creation resides in `distributed/parallel_state.py`,
the CPU helper `utils/system_utils.py:72`, and optional weight-transfer
helpers. The model, V2 speculator, graph, and KV-transfer subtree search found
only the PP broadcast sibling call above. `create_communicators` and
`ProcessGroupXCCL` have no definitions/calls in this Python tree: the native
PyTorch/oneCCL implementation is outside the inspected clean source.

Do not add a blanket pre-resume all-reduce across every coordinator. It
would initialize unused WORLD/EP groups, add allocations/work, and change
the memory identity without a demonstrated need. No source-visible active
late group requiring a warm collective was found in this configuration.
This conclusion does **not** prove that native XCCL/oneCCL never allocates
another communicator or internal resource for a different stream, operation,
dtype, or size during graph capture. The reported 64 MB collective on an
existing communicator supports reuse but is not a guarantee for this full
model. Keep the residual risk in README and TRACING-FEASIBILITY and treat
the next graph run as a diagnostic feasibility attempt, not a qualification.

## Pause and destruction ordering

On normal client completion, census `run_client` pauses tracing in its
`finally` block before returning; the supervisor's normal teardown then
requests API shutdown. Worker `shutdown` calls model/worker cleanup and then
`destroy_model_parallel` and `destroy_distributed_environment`
(`v1/executor/multiproc_executor.py:820-829`). Those destroy TP/DCP/PCP/PP/
DP/EP/EPLB (`parallel_state.py:2084-2120`), WORLD and default process group
(`:2123-2130`), via `GroupCoordinator.destroy` (`:1225-1233`). Thus normal
communicator destruction follows the pause. A worker crash can occur before
the normal pause. The original census watchdog also requested stop before
its finally pause; that exceptional race must not be described as proven
pause-before-destruction unless the supervisor is changed to order those
operations. Pausing does not unload the tracing layer, so the previously
reported native traced-exit crash remains possible even when paused.

## Relevant source SHA256

```
aa2b1f1f2c3bf9277f6cad3639ee7f76874485a171bf673a28a130553c16f218  vllm/v1/worker/gpu/model_runner.py
e7d59285879d3dce70d891b99e0e6892bd96ef93c3a4746b3fc723b5086df4d5  vllm/v1/worker/gpu_worker.py
dc0aa8e7a0e303e38fdaf2729d878e2c23678be1a2e56fd2d46599cf5181ad11  vllm/v1/worker/xpu_worker.py
07fa0390d28f2b8c3c3c0019eb9c3b126e2397aea268ba47c889f06b423deb23  vllm/v1/worker/xpu_model_runner.py
5951dc8c6e25f57c80fa4f4c5a55b8d5b39799a7fc578e36f9c98e89b9897af0  vllm/platforms/xpu.py
98d4fb7095d440ee5285a3742713c02865a494fe0e851f1b301f4861d1656cbb  vllm/distributed/parallel_state.py
```
