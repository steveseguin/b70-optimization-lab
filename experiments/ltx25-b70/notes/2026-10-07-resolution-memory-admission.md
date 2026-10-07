# Conservative admission for the first 640×384 native reference

Status: **CPU planning only; no new runtime admission or measured full-pipeline
memory bound.** Use the qualified packet99b 23/25 source/arithmetic control,
manifest `f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
The [reference design](2026-10-07-resolution-reference-design.md) remains the
quality protocol. Native requests are serial, B1, with 240/960 video tokens.
The proposed optimized comparison uses W1, sampler depth1 and decoder depth2,
with three fill prompts. This does not inherit a larger-resolution quality claim
from packet98 or authorize changing a sealed packet.

## Admission before the first native request

Implement a new identity-bound admission node after the host loader has made
the complete 23/25 sampler, latent upsampler and native video/audio VAEs
resident, and after the accepted graph-sharded text encoder and window workers
have been captured and qualified. Before **each** serial native fixture, record
fresh synchronized physical free bytes on all four cards and require:

| Card | Minimum physical free | Planning allowance above the 2 GiB floor |
| --- | ---: | ---: |
| xpu:0, primary sampler | 6 GiB | 4 GiB eager sampler/upsampler allowance |
| xpu:1, secondary sampler | 6 GiB | 4 GiB eager sampler allowance |
| xpu:2, primary text encoder | 2 GiB | Encoder graphs already resident |
| xpu:3, text shard and native VAEs | 7 GiB | 5 GiB native decode allowance |

Reject missing/nonfinite readings, wrong placement/dtype/resident identities,
changed encoder/window identity, installed sampler graph routes, decoder
replicas, or an existing fault. Check the actual reference objects rather than
assuming a loader's completion means every later allocation is resident. Do
not unload models or evict encoder graphs to make these checks pass. Preserve
the existing host-memory and health gates. No native operation precedes the
normal GPU health preflight.

These thresholds are **engineering allowances, not strict global peak bounds**.
The 4 GiB sampler allowance exceeds the old pooled-worker planning estimates
below, but those are different execution modes. The 5 GiB decode allowance
rounds upward from the entire historical 3.508 GiB decode peak plus 1 GiB. It
does not subtract already-resident VAE weights, deliberately double-counting
them rather than claiming a transferable scratch-only measurement. Card2's
floor assumes its accepted encoder graphs are already resident and the normal
qualified encoder path is retained; it does not prove zero replay transients.

If admission passes, permit **one bounded native measurement**, recording
before/after physical free, allocated/reserved memory and per-card allocation
peaks, alongside source, graph, request, conditioning and resident-model
identities. Peaks include existing resident allocations; report that baseline
instead of confusing total peak with incremental scratch. Review the first
result before admitting another fixture. A fault, OOM, observed floor violation,
unexpected eviction/ownership change or fallback attempt halts new requests.
There is no automatic retry, server cycle or memory-setting change. A sampled
free-memory floor cannot prove that no shorter transient dip occurred.

The later optimized capture/replica phase needs its **own** live admission and
same-size per-worker receipts. Passing native admission does not pre-admit
graph pools, replication or overlapping decoding.

## Measured evidence and its limits

The qualified99b 256×256 W2 freeze reports free memory of approximately
7.534/12.319/9.741/14.548 GiB on cards0/1/2/3. It includes the accepted text
encoder, sampler graphs and card2 decoder replica. This suggests room for the
proposed first measurement, but it is neither a live reading nor a 640 bound.
Do not credit removal of those graphs/replica as measured extra headroom.

The historical [resolution probe receipt](../data/resolution-cost/resolution-cost-01.json)
measured a BF16 **12-block** transformer on one card with seeded random
conditioning; the deployed model has48 blocks. Its 640×384 allocated peak was
14,322,492,928 bytes, with14,167,459,840 parameter bytes: a difference of
155,033,088 bytes (0.144 GiB). That difference does not bound a full sharded
native sampler, accepted conditioning, latent upsampling, allocator reservation
or coexistence with encoder graphs. No48-block peak is inferred from it.

The probe unloaded the transformer before loading both native VAEs. Full,
non-tiled video decode peaks were2,792,497,664 bytes at256×256 and
3,766,243,840 bytes at640×384 (3.508 GiB). Audio decode peaked at1,883,959,808
bytes; video and audio were measured serially. Both VAE weights are included,
but the sampler and text encoder are absent. The 640 result used25 frames,
BF16 compute and CPU outputs. It is not a current-source coexistence result.

The inherited packet98 pooled-worker planning formula gives1.7485/1.5330625
GiB for cards0/1 at640: old B1 worker increments0.2664/0.2281 GiB multiplied
by the3.75 token ratio and1.5, plus0.25 GiB. Those are planning estimates for
captured workers, **not native eager measurements or a proven upper bound**.

The actual99b native VAE estimator in `comfy/sd.py` is
`1700 * frames_latent * height_latent * width_latent * 512 * dtype_bytes`.
For `[1,128,4,12,20]` BF16 this is1,671,168,000 bytes (1.556 GiB). It is not
the whole observed VAE peak and cannot alone admit this experiment.

## Native VAE must refuse fallback

The concrete successor source location is:

`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/comfy/sd.py`

`VAE.decode` begins at line1262. Its `except Exception as e` calls
`model_management.raise_non_oom(e)` and then sets `do_tile = True`; the
following branch calls `soft_empty_cache()` before tiled decoding. The new
reference identity must make an OOM escape **inside that exception handler,
before the fallback flag/cache flush**, for the exact admitted native VAE
objects. Preserve unrelated behavior and propagate non-OOM exceptions. An
outer wrapper alone cannot catch an OOM already swallowed by this handler.
An estimator-triggered OOM must also abort, not select direct tiling.

Historical `scripts/probe-resolution-cost.py` around line359 replaces
`decode_tiled_1d`, `decode_tiled_`, `decode_tiled_3d` and `_decode_tiled_owned`
with refusal stubs. That proves the historical measurement excluded successful
tiling, but copying only those stubs would still allow the earlier cache flush.
Use the handler-level refusal for the new reference path; preserve the old
probe as evidence, not an execution recipe.

## Finite W1 storage budget

The four expected FP32 output tensors contain:

| Tensor | Bytes |
| --- | ---: |
| Images `[25,384,640,3]` | 73,728,000 |
| Video latent `[1,128,4,12,20]` | 491,520 |
| Audio latent `[1,8,26,16]` | 13,312 |
| Waveform `[1,2,48480]` | 387,840 |
| Total per full raw capture, before headers | **74,620,672** |

There are3 first native fixtures +3 independently executed repeats +3 optimized
candidate comparisons +10 emitted timed clips = **19 essential captures**
(1.320 GiB). Charge the three W1 fill prompts as full captures even if a fill
produces no tensors: **22 charged captures**. Reserve another10 full captures
for setup/probes, queued tails and any separately required fill sequence.
Thus **32 is the total permitted raw-capture budget**, not a prediction that
every request emits or permission to add uncounted capture/setup requests.
If the final graph schedule needs more than32, recompute admission beforehand.

Thirty-two raw captures cost2,387,861,504 bytes (**2.224 GiB**). Add512 MiB
previews,128 MiB logs,64 MiB metadata/headers and1 GiB cache allowance: total
approximately**3.912 GiB**, within the declared**4 GiB** write allowance.
Keep at most three bounded previews. At the coordinator-reported59 GiB free,
the4 GiB allowance leaves55 GiB, above the50 GiB filesystem floor. Recheck the
actual destination filesystem before creating outputs and between phases.

This is not capacity reservation or a hard bound on runtime/compiler cache
growth. Record actual output/cache growth; refuse new work when the declared
budget or50 GiB remaining-space floor would be exceeded. Retain all first-stage
references, repeats and failures. No deletion is part of this plan.

## Evidence identity

Paths below are relative to `experiments/ltx25-b70/`, except the sealed source.
These hashes record the files inspected for this note:

- `data/resolution-cost/resolution-cost-01.json`:
  `d317178f8958d0869427aa249660ee3c2b524261b348d3de73c26b53097ad7cc`
- `scripts/probe-resolution-cost.py`:
  `16e159344f138311b7f1bddc720f6b953a793bed991c620707b14e0b7d5fa285`
- `data/upstream-99b/two-way-w2-b1-p1-dxpu2-s256x256/sampler-capture-freeze-f99b-twowayw2b1p1dxpu2s256x256-freeze.json`:
  `f55bb175e112d4f7e3a3586251b9405d1af5622f281126be977544c1e9560edd`
- `scripts/worker-headroom-98.py`:
  `8dee8c4748a026ce1f4d1125ca50b67431a1d44921d33121addf6a4aa7d37944`
- `scripts/capture_node.py`:
  `6495b0c4de7ac054e35a39fb00e7c7b979d5fb51d6e77bc0dee18bad9d0ec9da`
- Sealed99b `source/comfy/sd.py` at the absolute path above:
  `2917a7982d08640ebe297ebc5cb5ad873567099c2e66688dcaff3650464dc694`

No implementation, source materialization, GPU request, model operation,
runtime mutation or host-setting change was performed to prepare this note.
