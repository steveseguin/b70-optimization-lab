# Next compiler gate: one native block in the persistent runtime

This is a source-only integration proposal, not a deployment or speed result.
The [real bound CPU capture](ltx-bound-lifecycle-capture-cpu.md) now qualifies one
tiny CPU case with the lifecycle object in the actual callback metadata.
Repeating that CPU exercise will not answer the next question: whether the
native 386,674,880-element block compiles on XPU with exact output, bounded
resources, and a useful warm latency reduction.

## Smallest runtime integration

The immutable `prepared-encoder-03` packet has five exact extension identities,
a startup whitelist, and an explicit compiler-excluded limitation. It cannot
execute the candidate through its existing supported nodes. Stock
`TorchCompileModel` does not supply the required boundary/options/guards. Do not
hot-import a node, modify the packet, or compile another full model alongside
the retained server merely to avoid acknowledging that source boundary.

Build one sealed successor packet with the compiler capability dormant during
encoder tests. If encoder-03 is already running, finish its finite screen first;
the successor is one planned process replacement, not a per-variant restart.
The user's ongoing optimization authorization covers ordinary implementation;
do not create another routine permission pause. Device ownership, faults, and
the no-restart-chain constraints still apply. This plan performs no replacement.

Keep the measured compiler source unchanged: base
`scripts/ltx_block_compile.py`, then
`patches/ltx-block-compile-ownership-guard.patch`, then
`patches/ltx-block-compile-pre-run-lifecycle-v2.patch` (not lifecycle v1).
The effective adapter hash is
`79ba260785e16d7e646bfe79b0816e99a8fab6db557a60408c35bd7675121577`.
Package it under `source/scripts`; a small custom-node facade must import that
module rather than load a second copy of its class definitions. Preserve the
existing shard helper's module identity for exact class checks.

The facade should expose `eager`, `compiled`, and `restored` modes, defaulting to
eager. Eager returns the original resident patcher. Compiled retains exactly one
candidate from `apply_block_compile(model, index=24)`. Restored returns the
clone from `remove_block_compile(candidate)`. The source registration and native
block forward remain untouched. Block 24 is on XPU1 in the measured 21/27 split
and matches the selected block in the bound CPU capture.

With `--cache-none`, Comfy nodes execute again every request. Therefore the
facade must retain the candidate explicitly, keyed to the original resident
patcher/model identity and fixed selected index; otherwise each request creates
another compiler wrapper. Permit only one such key per screen and reject model
or component-generation changes once it exists. Hold the encoder variant fixed
through this screen. Never cache conditioning, block outputs, or generated
frames. This avoids a new reload/unload policy and keeps control clones intact.

Add node `422` after resident node `420`, taking `model: ['420', 0]`. Change
**both** `388.inputs.model` and `391.inputs.model` to `['422', 0]` so one callback
serves the original 8-step and 3-step stages. Keep node 421 placement validation,
24 fps, 25 frames, minimum 256x256 final output, all seeds, native BF16, noise,
samplers, and all four capture tensors unchanged. Changing only one guider
would test only one stage.

## Required new files and packet changes

These are proposed implementation interfaces, not already available commands:

- `scripts/block_compile_node.py`: bounded resident candidate facade and
  exclusive per-request compiler receipt; use the measured adapter above.
- `scripts/prepare-block-compile-runtime.py`: successor packet builder, preserving
  encoder-03 and inventorying the effective adapter, facade, patch inputs,
  compiler graphs, and copied launcher/common files.
- A packet-local identity checker and launch whitelist that include both new
  helper hashes and the facade custom node. Preserve endpoint identity equality,
  source/runtime/model hashes, process start ticks, boot ID, strict determinism,
  fault checks, and external mutable run/cache paths. Set one compiler worker
  before Torch import; place compiler caches under the new server run directory,
  never under sealed packet source. No graph/forced-communication changes.
- `scripts/run-block-compile-screen.py`: compiler-specific finite client using
  frozen `profile-clip.py` and `compare-clip.py` through subprocess, plus the
  original retention/memory helpers. The frozen encoder client hardcodes five
  extension names and encoder-only graph deltas, so it cannot simply accept this
  successor without a new client. Do not weaken its old identity rules.

## Bounded native gate and evidence

Use at most seven sequential requests, with one encoder variant chosen from the
completed screen: eager boat; compiled initialization boat; compiled warm boat;
compiled marble; compiled bird; compiled boat repeat; restored eager boat.
Compare all four output archives against their protected original oracle
immediately after **every** request, including both initialization requests.
No next request after mismatch, compile failure, OOM, identity change, timeout,
or device fault. The existing profile helper supports `--timeout 600`; a client
timeout is not proof server work stopped. Record it, halt submissions, and
inspect the existing process; never restart or resubmit automatically.

The first compiled boat is the actual native-weight qualification gate. Run
the unchanged adapter with fullgraph=True, dynamic=False, all guards intact,
one compiler worker, rounding-preservation options, no autotuning, and no CUDA
graphs. Snapshot actual registered native state after loading: names, shapes,
dtypes, device, bytes, owner identities and selected route. Expect BF16 from
the audited static loader; fail rather than cast if actual state disagrees.
Record actual native input signatures for both stages rather than inferring
them from the tiny CPU fixture. Record compiler coverage/counter deltas and
break/fallback evidence. Two stage graphs are the intended screen; additional
specialization is a recorded failure needing review, not permission to strip
metadata/guards or sweep options. Check counters between block dispatches so
unexpected repeated compilation cannot grow across the remaining requests.

Full-clip oracle equality is sufficient for this first bounded end-to-end gate;
do not add a second eager execution inside every native block call. If a later
mismatch needs direct block-local diagnosis, note that native `forward` mutates
both input streams (`add_`/`addcmul_`, av_model.py lines 286 onward). Eager and
compiled calls must receive independent copies of mutable input tensors with
alias relationships respected; reusing the same inputs would invalidate the
comparison. Such a diagnostic is separate from warm timing.

Record compilation-inclusive initialization separately from warm preview,
raw-output, and client-completion latency. Read current host MemAvailable and
per-device free/allocated/reserved memory before the gate and at each request;
native compiler peak memory remains unknown. The stored block is 737.71 MiB,
but that is not a compiler workspace bound. Do not increase GPU reservation,
offload existing components, or alter power/swap/cache settings to force a pass.
One block cannot establish full-model speedup or a safe 48-block memory budget.

Retain small JSON/log receipts, graph identities, compiler cache inventory/size,
and at most three exact-verified previews; preserve failed evidence and protected
oracle tensors. Prune successful raw candidates only after exact verification.
Restoration is dispatch-only: parents and route/guard references retain compiler
state. No claim of reclaimed compiler/GPU memory and no global Dynamo reset.

The immediate implementation blocker is the missing source-packet node and its
identity/client integration. The next experimental blocker is native-weight XPU
capture and exactness, not another synthetic CPU lifecycle audit. Only after
that gate passes should measured warm results determine whether to compile more
blocks or choose a different optimization.
