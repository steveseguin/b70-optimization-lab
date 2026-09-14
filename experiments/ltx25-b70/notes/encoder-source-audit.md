# Encoder exact-output candidates, September 13, 2026

Status: source audit and CPU emulation only. Neither patch is applied to the
source checkout or running server. No GPU requests or process changes were
made by this audit. Root owns the separate stability campaign.

Source pin: ComfyUI `19e1058f4c445ef74047e77a23f9ca7684c1e4b6`, locally
`/home/steve/src/ComfyUI-ltx25-baseline`. Line references below refer to that
unmodified pin. Both patches pass `git apply --check` against it.

Runnable CPU reproducer: [test-encoder-candidates.py](../scripts/test-encoder-candidates.py).
It reads the exact pinned source through `git show`, applies the two tracked
patches in memory with strict context checks, and extracts the actual methods
through Python AST. It never modifies the checkout or imports ComfyUI. Run:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/test-encoder-candidates.py
```

Result: **11/11 tests passed**, including the five crop fixtures and unchanged
defaults, the LTX opt-in call, accounting drift reproduction/correction,
explicit partial unload, a larger budget, and the changed-device guard. The
accounting tests use fake modules/devices with empty parameter dictionaries;
they exercise the extracted control flow, not real weight storage or XPU.

A second [real-parameter CPU lifecycle suite](../scripts/test-encoder-accounting-lifecycle.py)
imports the actual ComfyUI ModelPatcher with `--cpu`, dynamic VRAM disabled,
pinned memory disabled and asynchronous offload disabled. It installs the
candidate method only on an in-process subclass, leaving the imported base
class and source files unchanged. Run:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/test-encoder-accounting-lifecycle.py
```

Result: **7/7 tests passed** with real BF16 `comfy.ops.manual_cast.Linear`
parameters, parameter SHA256 checks and exact small-model outputs. Coverage
includes repeated `partially_load`, original-counter disagreement, explicit
partial unload/full reload, detach/reload, changed patch UUID, forced patch
reapplication without doubling a nonzero delta, restoration of original
weights, and a mixed standard LayerNorm/manual-cast Linear model. A changed
UUID with the candidate produces the same parameter hashes and output as a
fresh stock full-load patch application. CPU load and offload are the same
physical device, so this validates lifecycle bookkeeping and weight
preservation, **not accelerator residency or transfer behavior**.

## First priority: apparent encoder residency accounting drift

The existing speed-server log reports encoder loaded/offloaded MiB as
24541/457.51, then 24489/510, 24444/555, 24399/600, and 24354/645. The repeated
45 MiB decrease equals its reported reserved offload buffer. **This is not
proof of increasing physical offload, a memory leak, or a latency regression.**

The pinned source contains a mechanism reproducing that report drift:

1. `comfy/sd.py:462` calls `load_models_gpu` again for every encoding.
2. `comfy/model_management.py:1008` adds reported loaded memory to free memory
   when choosing a budget, then subtracts it to obtain additional memory.
   Zero additional memory becomes the 0.1-byte sentinel at line1015.
3. `comfy/model_patcher.py:1277` calls `load` again with current loaded bytes
   plus that extra budget. `load` starts its counter at zero, then reserves
   the offload buffer again in its fit test at lines1000–1001.
4. A previously resident module can now fail that fit test. It is omitted
   from `mem_counter` and labeled low VRAM. The corresponding `offloaded`
   handling at lines1084–1089 only pins parameters; it does not move the
   newly excluded resident module to CPU. Thus the reported loaded-byte
   counter can shrink while the actual allocation stays resident.
5. The next call starts from that smaller reported counter and repeats.

CPU execution of the **actual extracted pinned `ModelPatcher.load` method**,
using four fake 45-unit modules and a fake device, reproduced this:

| Iteration | Load budget | Reported resident | Actual fake-device resident |
| --- | ---: | ---: | ---: |
| Initial | 145 | 90 | 90 |
| Repeat1 | 90.1 | 45 | 90 |
| Repeat2 | 45.1 | 0 | 90 |
| Repeat3 | 0.1 | 0 | 90 |

The [accounting candidate](../patches/encoder-resident-accounting.patch)
preserves the resident classification of modules already patched on the same
device. Actual offloading remains the responsibility of `partially_unload`,
which already moves weights and updates accounting at lines1218–1252.
The same emulation with the candidate reports 90 actual/90 accounted units
on all four iterations. It does not change numerical operations.

The extracted `partially_unload` method also releases one fake module and
keeps the corrected count aligned; a larger budget loads the remaining fake
modules. The changed-device test verifies that the candidate's exemption does
not apply when the model's prior device differs. That test intentionally does
not qualify retargeting a partially loaded real model: its minimal fixture
retains a module on the prior fake device, matching upstream's limited behavior.

This candidate touches a generic ModelPatcher method and remains unpromoted.
The real-parameter suite above now covers basic weight storage, changed patch
UUIDs, forced patching and mixed leaf modules. Hooks, quantized/custom storage,
actual cross-device movement and concurrent use remain outside its scope.
Review that retaining an already resident
module cannot bypass an intended release. On GPU, record actual per-device
allocations and per-parameter residency alongside the reported counter; only
those measurements establish the live mechanism. The current fdinfo campaign
can test physical memory trends but cannot inspect Python parameter devices.
Do not claim this correction removes the initial true 457 MiB offload.

Patch SHA256:
`14a28f05e6bb5988ee86a511d4558ab4721bf2e59a8cc202601b660c01aef456`.

## Next latency candidate: crop unused hidden states before their CPU copy

The LTX Gemma tokenizer retains a minimum length of 1024 tokens
(`comfy/text_encoders/lt.py:83–90`). Gemma4 12B has 48 layers and hidden width
3840 (`comfy/text_encoders/gemma4.py:98–112`). Its all-layer path retains 49
states, including the final normalized state (lines565–567 and639–643).
`SDClipModel.forward` casts them to FP32 (`comfy/sd1_clip.py:284`).

`ClipTokenWeightEncoder.encode_token_weights` concatenates those states and
copies them to the intermediate device, CPU in this launcher
(`comfy/sd1_clip.py:65–68`; `comfy/model_management.py:1251`). Only afterward
does LTX crop to the valid-token suffix and transfer that suffix back to the
encoder GPU in BF16 for projection (`comfy/text_encoders/lt.py:183–187`).
For a single 1024-token section the untrimmed FP32 transfer is
49 × 1024 × 3840 × 4 = **770,703,360 bytes, or 735 MiB**.
The current node timing includes this path; its precise latency contribution
has not been separately measured.

The [crop candidate](../patches/encoder-crop-before-cpu.patch) adds an opt-in
keyword to the common token-weight wrapper, enabled only by the LTX call.
It crops the final concatenated hidden-state tensor before copying it to CPU.
The original LTX crop stays in place and becomes a redundant slice. The
encoder still evaluates all padded tokens, retains all layers, uses the same
FP32 intermediate values and BF16 projection conversion, and returns the
same mask and metadata. Other callers keep their original behavior.

Five small synthetic CPU cases passed exact equality against the original
method followed by the existing LTX crop: one section with 3 valid tokens,
one with all 8 valid, a zero-valid mask, two sections with 5 valid each, and
the empty-section path. All five also passed unchanged-default behavior.
Zero valid tokens intentionally preserve Python's original `-0` slice
semantics. These are copy/slice checks, **not full-model XPU parity evidence**.

Possible benefit applies to freshly encoded prompts as well as repeated
ones. This is not prompt conditioning reuse. It also does not remove padded
token computation; changing padding or sequence geometry could select
different arithmetic and is a separate candidate requiring its own oracle.

Patch SHA256:
`2c319f597549e638a65437a3e5af360d9a5b16260884f767cdc80662cf101f9d`.

## Why the initial encoder offload exists

The LTX estimator has a 642-token floor and 3 MiB/token coefficient for BF16
(`comfy/text_encoders/lt.py:244–254`), reserving 1926 MiB even for short text.
The launcher also reserves 6 GiB. `load_models_gpu` combines these at
`comfy/model_management.py:930`. Consequently its ~24.4 GiB encoder does not
fully fit the permitted weight budget despite a dedicated 32 GiB card.
Do not reduce the user's stability reserve or change global memory settings
to evade this estimate.

A later topology candidate is to register the existing dual projection on
XPU3 alongside the VAEs, retaining the Gemma transformer on XPU2. Projection
weight dimensions are large enough to be relevant to the residency budget,
but exact local weight bytes and per-device peaks must be inventoried before
building this. Use real ownership and normal ModelPatchers, as with the
accepted diffusion split. Do not leave hidden CPU weights behind a nominal
device label. This is a preparation idea, not an implemented patch.

## Live-node possibilities and gates

No stock registered graph node exposes this crop or ModelPatcher accounting
correction. The loaded extension has no supported live reload. Applying a
patch on disk does not alter the running Python process. Keep these prepared
for a reviewed future deployment; do not restart this stability campaign.
`SelectCLIPDevice` is unsuitable: at `comfy_extras/nodes_multigpu.py:276` it
replaces the cloned patcher, without updating `clip.cond_stage_model`, and
does not expose the needed accounting/cropping option anyway.

BasicGuider was already screened exact and neutral. Sharing one encoding
among multiple graph branches could amortize conditioning work for an
unchanged prompt, but cannot be presented as faster fresh-prompt response.
There is no measured stock-node path to subsecond output here.

For any deployed candidate, preserve BF16, 256×256 minimum output, 25 frames
at 24 fps, both seeds and the unchanged 8+3 sampling schedule. Require exact
conditioning tensors first, then all four final output tensors against the
frozen boat/marble/bird references, and three same-identity repeats. Include
short/long prompts for crop testing. Bind code, graph, model hashes and actual
device placement; record fresh-prompt latency separately from reusable
conditioning throughput. Maintain bounded media retention. Stop new requests
on the first device fault; no restart, power, swap or cache manipulation.
