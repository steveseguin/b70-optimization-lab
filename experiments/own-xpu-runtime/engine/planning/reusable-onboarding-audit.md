# Reusable engine onboarding audit

Read-only source review, 2026-10-25. This distinguishes implemented interfaces
from admitted model capabilities and hardware qualification. The owner prohibits
draft training; future work uses existing weights and measured inference tuning.

## What is already reusable

The ring ledger and wire protocol take context length, vocabulary, stage count,
request identity and negotiated F32 stream extent as inputs. They do not encode
SC117's 48 layers, hidden width, vocabulary or a four-card split. See
[src/pipeline/ring/stage_ring.hpp](../src/pipeline/ring/stage_ring.hpp),
[wire.hpp](../src/pipeline/ring/wire.hpp),
[ring_coordinator.py](ring_coordinator.py) and
[tools/ring_wire.py](../tools/ring_wire.py). First/final ownership, immutable row
and parent identities, oldest-only acceptance and suffix rollback are separate
from model arithmetic. CPU coordinator and socket fixtures cover 2/4/6 owners.
A six-owner CPU fixture is not a six-GPU qualification.

The coordinator admits at most three unresolved global rows and two tentative
rows per early stage. Completed stream payloads are released when all owners
accept a row; lineage metadata remains. The long-prompt test checks retained
payload bounds while other commands still hold immutable input publications.
The existing boundary is a bounded full F32 stream, not a fixed SC117 width.

[placement.py](placement.py) inventories per-tensor quant IDs and dimensions,
checks contiguous layers, and proposes 1/2/4/6 contiguous partitions. Optional
measured costs bind placement, runtime, measurement and workload identities.
Neither parsing a quant ID nor proposing a partition admits a decoder, proves
memory fit or establishes speed.

[deployment/prepare.py](../deployment/prepare.py) already separates trusted
content hashes and descriptors from local file paths/stat bindings. Relocation
creates a generated authority overlay and build receipt without replacing the
canonical source. Model authenticity and local deployment identity remain
separate from GPU ownership and run permission.

## Current support must remain explicit

The shipped immutable profile is specifically SC117 IQ3_S with its admitted
`qwen4exp` architecture, F32 activation lane, 4096-token native context and
existing official FP8 draft. The portable launch recipe supports two/four B70
owners; the model's default single-card residency is not claimed. Two/four-card
native proofs and measurements are recorded in the research ledgers. They do
not establish arbitrary-quant/model support, six-card performance or clean-host
portability. The new ring's hardware proof is a separate qualification gate;
its scripted oracle-assisted proposal mode cannot establish live-draft speed.
Internal GPU parity does not resolve the six independent CPU-reference
disagreements.

## Ordered implementation gates

1. **Select independently authenticated model and launch profiles.**
   [launch_plan.py](../deployment/launch_plan.py) currently pins a single
   `profiles/sc117-iq3s` directory and launch-policy SHA in code. Its
   [launch policy](../profiles/sc117-iq3s/launch-policy.json) already separates
   dispatch, per-model EOS/vocabulary, arithmetic flags, draft tuning and stage
   cuts from local BDFs and paths. A next profile version should accept an explicit
   profile path/hash and a separately trusted policy path/hash, require their
   model-hash association, and retain the current SC117 profile as a qualified
   option. A profile import tool must preserve full shard, header, descriptor,
   tokenizer/template and draft identities. Renaming a profile is not onboarding.

2. **Declare geometry and decoder capabilities before another quant/model.**
   `prepare.py::parse_placement` currently bounds `layer < 48` and historical
   placement masks to `<= 3`; `load_profile` explicitly requires `qwen4exp`,
   context 4096 and F32. These are honest current capability checks. Introduce
   authenticated geometry and a supported decoder/shape inventory before changing
   them. Validate actual per-tensor storage type and shape against that inventory,
   then qualify a second quant of the same architecture. Preserve old arithmetic
   and dispatch choices. A different layer count, attention family, recurrent
   layout or DeepSeek architecture requires a separate native capability path
   and independent reference fixtures; relaxing the current checks would not
   supply that implementation. Native retained tuned kernels still have
   SC117-specific shapes and flags in
   [main.cpp](../src/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp).

3. **Promote topology policy independently of the scheduler.**
   `launch_plan.py` admits only 2/4 BDFs, selects cuts from policy, and emits
   legacy `--target-split 23`; portable legacy MTP is two-rank only and capped
   at 128 outputs. General pipeline/live paths have a separate 512-output cap.
   The ring controller currently admits 2/4/6 stage counts, but the portable
   profile has no six-stage policy. First add measured six-stage cuts and a
   memory budget, then qualify execution. One-owner support needs its own
   admission/controller path: the ring coordinator deliberately requires at
   least two owners. Do not present the metadata planner's one-GPU proposal as
   an existing runnable configuration. Keep generic native layer slicing and
   first/final ownership in [layout.hpp](../src/pipeline/layout.hpp).

4. **Make resource limits visible when expanding geometry.**
   The wire intentionally caps each F32 boundary stream at 64 KiB; larger
   architectures require a negotiated/versioned mapping, not unchecked writes
   or silent BF16 conversion. The ring checkpoint reserves two images with a
   512 MiB combined backup/table cap in
   [checkpoint_ring.hpp](../src/pipeline/ring/checkpoint_ring.hpp). The portable
   launcher currently applies a 31 GB packed-weight planning bound per B70;
   that excludes KV/recurrent/activation/scratch, draft weights, checkpoint
   images and host shadow memory. Another quant or context must account for
   those allocations and actual available VRAM/RAM before execution. Resource
   bounds are legitimate refusal conditions, not architecture dimensions to
   remove indiscriminately.

5. **Measure a new quant before choosing its tuning profile.**
   `placement.py` explicitly excludes global/head work, host lookups, expansion,
   communication and pipeline bubbles unless supplied as measured overheads.
   Capture per-layer and stage-overhead timing with matching model hash,
   arithmetic, context, workload, engine and topology identities. Record cold
   prompt behavior, full output hashes and exact-state qualification separately
   from diagnostic timing. Packed bytes alone are a placement estimate. Draft
   prefix limits and kernel choices in the current policy must be remeasured for
   a new vocabulary/quant rather than copied as universally optimal defaults.

6. **Connect the ring to the portable lifecycle after its own state proof.**
   [ring_driver.py](../tools/ring_driver.py) currently reuses the lab
   `pipeline_driver` plan and passive observer. Its scripted native proof is not
   a portable deployment entrypoint. [portable_live.py](../deployment/portable_live.py)
   already demonstrates injecting the credential-agnostic portable Guard and
   explicit lifecycle for the existing live path. Use that pattern for ring
   planning/execution after qualification; do not package lab credentials,
   historical adapter plans or absolute host state. Add the new modules to the
   explicit source-bundle closure only with extracted-tree import tests and
   pinned build/profile/state evidence. Persistent portable serving and clean-host
   toolchain installation remain separate work from a one-shot proof recipe.

No active source, capability check, service, GPU setting or process was changed
for this audit. The ordered gates preserve the existing SC117 recipes and
negative results while making the next model's unsupported assumptions visible.
