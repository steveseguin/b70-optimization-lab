# Codex read-only review, packet 91b (2026-10-03)

Final answer of `codex exec -s read-only`; the prompt and the fixes that followed are in the packet build notes.

Reviewed through `2855ca308`, read-only. No servers, GPU operations, or file changes.

**Confirmed defects/gaps first:**

- **Placement switching can still lose a clip.** The sampler has already submitted the current job and consumed its predecessor before the decode guard refuses the change ([sampler:331](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/pipeline_sampler_node.py:331), [collection:198](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_pipeline.py:198), [guard:455](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/pipeline_decode_node.py:455)). That predecessor never gets decoded. Continuing skips it; retrying the same index hits the stale-job check. The guard must precede upstream consumption.
- **Writer starvation remains possible** in the existing RW lock: incoming readers check only an *active* writer, so they can repeatedly bypass a waiting capture ([lock:489](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_graph_capture.py:489)). This is a fairness defect, not evidence this finite campaign will hang.
- **Cleanup’s device-scope claim is false.** `empty_cache()` affects all devices, despite the xpu:1 context ([cleanup:300](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_decode_replica.py:300)). The [pinned PyTorch allocator](https://github.com/pytorch/pytorch/blob/08187d9e0fba026dc8217405802ab5381dc88d90/c10/xpu/XPUCachingAllocator.cpp#L1953) iterates device allocators, causing cross-card synchronization/cache perturbation.
- **First-copy failure skips cache cleanup:** registration happens only after construction returns; if the first copy throws, `_REPLICAS` remains empty and cleanup is skipped ([construction:601](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/pipeline_decode_node.py:601), [cleanup condition:640](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/pipeline_decode_node.py:640)). References unwind, but reserved allocator memory can remain.

**A — Fix status:** (1) fixed: both replica decode callers take shared CAPTURE; (2) registered replicas are released on negative/error verdicts, with the first-copy caveat above; (3) fixed through `named_buffers()`, including nonpersistent buffers ([verification:186](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_decode_replica.py:186)); (4) fixed: queued previews produce status text ([record:506](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/pipeline_decode_node.py:506)); (5) incomplete, as above.

**B — Lock orders** (`S` = shared CAPTURE, `X` = exclusive CAPTURE):

| Thread/path | Acquisition order |
|---|---|
| Both samplers | Pipeline `_LOCK`/condition, `_ACTIVE_LOCK`, `_NOISE_LOCK`, `_LOAD_LOCK`, and registry lock are released before graph execution; then `X` for capture or `S` for replay. |
| Encode worker / inline encode | `_LOAD_LOCK` during loading, released; then per-layer `X` or `S`. |
| Native decode worker / probe native callback | `_NATIVE_LOCK → _LOAD_LOCK`; no CAPTURE in original VAE mode. |
| Replica decode worker / probe replica callback | `_REPLICA_LOCK → S → video Replica.lock`, then audio `Replica.lock` separately. |
| Probe construction / release | Construction: `_LOAD_LOCK → S`. Release: `_REPLICA_LOCK → S` around `empty_cache`; reference clearing/GC precedes `S`. |
| Writer | Decode locks released before submission. Writer `self.lock` protects startup/records; queue mutex/conditions protect enqueue/dequeue. Neither spans encoding or blocking queue waits. |

Evidence: [sampler graph locks:927](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_graph_capture.py:927), [encoder:324](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_graph_text_encoder.py:324), [decode:284](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/pipeline_decode_node.py:284), [replica:221](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_decode_replica.py:221), [pipeline:138](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_pipeline.py:138), [writer:163](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/pipeline_decode_node.py:163).

CAPTURE’s internal condition releases its mutex while waiting. `_BUSY_LOCK` is bypassed with `LTX_BUSY_WINDOWS=0`. **No acquisition cycle, shared-wait inversion, nested-reader/queued-writer deadlock, or ordinary exception-path lock leak found.** The current RW implementation admits nested readers despite a queued writer; starvation is its problem.

**C — No live graph-pool freeing defect found.** Active graph pools remain protected by allocator ownership. Cleanup **can overlap sampler replay**, because both use shared mode; replay also releases the lock after submission. The [allocator releases private pools only after their use count reaches zero](https://github.com/pytorch/pytorch/blob/08187d9e0fba026dc8217405802ab5381dc88d90/c10/xpu/XPUCachingAllocator.cpp#L1093).

**D — No unsafe-stop defect found in this runner’s campaign.** Arm timeouts/errors leave the server up. A still-running probe blocks control submission’s queue check. Shutdown requires empty queue, every expected sample/decode/save marker, then another fault/queue check ([runner:113](/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-91b.sh:113)). Fresh arm indices avoid the placement-switch defect.

**E — No new numerical/output-byte defect found.** Arithmetic and casts are unchanged. The placement refusal can omit an output clip; byte identity under concurrent execution remains a runtime gate, not something this static review proves.
