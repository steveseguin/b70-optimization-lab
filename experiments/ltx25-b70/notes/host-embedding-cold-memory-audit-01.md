# Cold component assembly: source-derived host RAM admission

2026-09-14. Recommended preflight floor: **103,102,806,218 bytes of MemAvailable (96.021970937 GiB)** immediately before the first component request. This is the largest audited model-storage overlap plus the existing8GiB operational margin. It is not a measured total peak, a universal hard bound, or a promise that unrelated host activity cannot exhaust RAM after admission.

This audit read frozen source, existing receipts and safetensors headers only. It imported no Torch/native modules, allocated no model tensors, queried no devices and touched no endpoint or process. Qualified residentv2, its memory helper and packet11 remain unchanged. The [structured contract](../data/host-embedding-cold-memory-contract-01.json), SHA `f596d6b4ad0f83efce39342a0d4a897aedd267e7df0f2f23f4403e704cb96058`, binds five checkpoint header/extent inventories, source hashes, saved model verification and original registered diffusion evidence.

## Dominant lifetime overlap

The resident's initial construction order remains UNET→CPU CLIP→video VAE→audio VAE→upscaler→layer-shard registration. These calls construct models; actual sampling/loading occurs later. The diffusion object is strongly retained in `_pending` and the local `model` while CLIP is built. Thus the CLIP-only constructor budget is insufficient as a cold preflight before the first UNET allocation.

The plain diffusion checkpoint contains42,017,512,960 tensor bytes:41,998,589,440BF16 and18,923,520F32. The saved actual sharded registration totals42,008,091,200B. Using the larger checkpoint payload as its retained CPU-state budget adds9,421,760B conservatism. The pinned BF16 configuration is passed into `model_config.set_inference_dtype`, through `LTXAV.get_model` and `BaseModel` into the native model constructor. Static `assign=False` state loading copies checkpoint values into parameter storage.

CLIP then holds both its26,263,774,294B checkpoint payload and26,231,584,372B of constructed registered state. The checkpoint count includes32,191,478U8 bytes of tokenizer data; the registered-state count includes1,552B of nonpersistent buffers. Therefore the dominant tracked overlap is:

```
  42,017,512,960  live CPU diffusion budget
+ 26,263,774,294  CLIP checkpoint tensor payload
+ 26,231,584,372  constructed CLIP registered state
= 94,512,871,626  tracked cold overlap
+  8,589,934,592  existing operational headroom
=103,102,806,218  required MemAvailable
```

The8GiB is an explicitly inherited operational margin. It is not a source-derived theorem about tokenizer, allocator or driver overhead.

## Other stages

| Construction stage | Conservative tracked overlap, bytes |
| --- | ---: |
| UNET checkpoint + header-budgeted BF16 destination | 84,035,025,920 |
| Retained UNET + CLIP checkpoint + registered destination | **94,512,871,626** |
| Retained UNET/CLIP + video VAE checkpoint/F32/BF16 overlap | 74,137,664,508 |
| Retained previous models + audio VAE checkpoint/F32/BF16 overlap | 71,179,906,598 |
| Retained previous models + upscaler checkpoint/F32/BF16 overlap | 74,068,849,226 |
| All constructed components at layer-shard registration | 71,081,641,802 |

Video VAE, audio VAE and upscaler checkpoint payloads are1,472,141,794B,364,666,868B and995,735,808B, respectively, all BF16. Their constructors can initially use F32 before `.to(BF16)` and static state copy. The table conservatively counts the full F32 constructor, full BF16 destination and full source checkpoint simultaneously for the model being constructed. Per-parameter casting normally releases old parameter storage progressively; no such credit is required for these stage comparisons. These rows budget checkpoint-corresponding tensor storage, not every auxiliary allocation.

## Source ownership and release

`UNETLoader.load_unet` calls `comfy.sd.load_diffusion_model`; its temporary state dictionaries share tensor references or move keys. `LTXAV.get_model` does not retain the supplied state dictionary. Its inherited `process_unet_state_dict` is the identity function. `BaseModel.load_model_weights` builds `to_load` from popped values, calls static `load_state_dict`, then deletes that temporary. The returned patcher's cached factory contains path/options rather than checkpoint tensors. No full original UNET checkpoint alias is intentionally retained into CLIP construction.

`load_clip` retains its checkpoint list during construction; the static CLIP path propagates `assign=False`. Prefix dictionaries share values rather than copying an entire checkpoint. Any tokenizer payload retained after construction remains an overhead limitation, but the complete checkpoint payload is already included at the dominant stage.

The resident deletes each VAE's `weights` dictionary after the VAE constructor returns. The VAE constructor first creates its architecture, then converts to the selected dtype and loads static weights. The LTX upscaler follows the same F32 construction→dtype conversion→static state-copy structure. Its local checkpoint dictionary ends with the loader call. Source inspection found no additional deliberate full-checkpoint cache for these models.

Layer sharding rearranges references and registered ownership between two patchers. It verifies that tensor identities/dtypes/shapes are unchanged; it does not copy model storage. The unregistered full-block tuple and registered partitions share the same existing modules, so they must not be added again to the memory budget.

## Required preflight location and conditions

Keep the qualified resident unchanged. Add a separate stdlib client admission after verified packet/runtime/server identity and an idle-queue check, immediately before submitting r01. Require no existing component-generation receipt, verify the original graph and forced BF16/static/mmap policies, compare MemAvailable against the exact floor, and write an exclusive identity-bound receipt before any model request. A startup check may supplement this, but a much earlier observation must not replace the final pre-request check.

Suggested receipt schema: `ltx.host-embedding-cold-memory-admission.v1`, stage `before-initial-component-allocation`, contract SHA, server identity SHA, exact required bytes, raw `/proc/meminfo` plus parsed byte fields, `passed`, and `swap_counted_as_headroom=false`. Missing or malformed observations, changed source/header/config identities, a busy queue, previous initialization or insufficient memory must refuse submission. No retries, pressure-inducing probes or floor reductions are implied.

This cold check supplements the qualified resident's separate restore and replacement-construction gates; it does not replace them. It also does not replace per-request full-residency, strict determinism or four-output parity checks. The source budget assumes the original model configs, plain checkpoints, fixed precision and unchanged construction order. Different precision, dynamic assignment, mmap policy or loaders require a new contract.

## Limits of the bound

There is no complete source-only bound here on retained allocator arenas, tokenizer object expansion, auxiliary/unregistered buffers, GPU driver allocations or concurrent system activity. Safetensors mappings are reclaimable; the budget counts source pages conservatively and credits neither swap nor guaranteed reclaim. Header geometry alone would be insufficient for arbitrary mismatched architectures; this contract additionally binds the audited implementation, original model verification and prior registered-state evidence.

The historical initial server VmHWM of98,758,332KiB was a whole-initialization observation, not an isolated cold-assembly maximum. It is evidence that cold initialization was already memory-intensive, not a measurement that proves this new floor sufficient. The floor is a conservative admission policy for the audited tensor overlap with a declared margin. Native memory behavior must remain observed, and faults or allocation failures must stop further requests.
