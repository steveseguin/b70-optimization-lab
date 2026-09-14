# One-block compile: executing-patcher lifecycle CPU gate

The inactive v2 candidate passed **25 CPU lifecycle checks** using native
`ModelPatcher.pre_run()` and a compiler dispatch spy. It rejects replacement of
the whole model, diffusion owner, or secondary owner; late patcher changes;
missing/foreign lifecycle callbacks; stale successful pre-run state after a
failed pre-run; and dispatch after native cleanup. Parent and sibling ownership
and restored eager dispatch remain intact. This is a lifecycle result, with no
video, throughput, XPU execution, or new compiled numerical-parity result.

Apply [ownership guard](../patches/ltx-block-compile-ownership-guard.patch) first
to the preserved base `scripts/ltx_block_compile.py`, then
[lifecycle v2](../patches/ltx-block-compile-pre-run-lifecycle-v2.patch).
**v2 replaces the initial lifecycle patch; do not stack both lifecycle patches.**
The test applies these only in a temporary directory. No core, running server,
encoder packet, or committed base adapter was changed.

The guard runs first in the expected native pre-run callback list, followed by
the original placement callback. It binds module owners without holding a
strong patcher reference, validates the executing patcher through native
`model.current_patcher`, and requires a successful pre-run for that patcher.
Bound dispatch revalidates before routing and before the compiled callable.
The v2 change clears the previous success before each pre-run validation.

## Evidence and reproduction

- [Current CPU test](../scripts/test-ltx-block-compile-lifecycle-v2.py),
  [receipt 02](../data/ltx-block-compile-lifecycle-cpu-02.json), and
  [log 02](../data/ltx-block-compile-lifecycle-cpu-02.log): passed 25/25,
  process exit 0; parent peak RSS 842,432 KiB. Torch `2.14.0+xpu`, CPU fixtures,
  one CPU thread, no compilation. The receipt records all source hashes.
- Current patch SHA256:
  `76a8445b14e9539f1d0277ffe2c964803a33afaa7372eb3e32e4571a3844a01b`.
  Effective adapter SHA256:
  `79ba260785e16d7e646bfe79b0816e99a8fab6db557a60408c35bd7675121577`.
- Frozen ComfyUI source commit:
  `19e1058f4c445ef74047e77a23f9ca7684c1e4b6`.
  Both receipts' source hashes were checked against disk after completion and
  still match.

From the repository root, using a **new** receipt/log name if reproducing:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python experiments/ltx25-b70/scripts/test-ltx-block-compile-lifecycle-v2.py --output experiments/ltx25-b70/data/ltx-block-compile-lifecycle-cpu-NEW.json > experiments/ltx25-b70/data/ltx-block-compile-lifecycle-cpu-NEW.log 2>&1
```

The [initial patch](../patches/ltx-block-compile-pre-run-lifecycle.patch),
[initial test](../scripts/test-ltx-block-compile-lifecycle.py),
[receipt 01](../data/ltx-block-compile-lifecycle-cpu-01.json), and
[log 01](../data/ltx-block-compile-lifecycle-cpu-01.log) are preserved unchanged.
Run 01 completed 22 lifecycle checks and was deliberately interrupted with
SIGINT (exit 130) after root's late scope clarification excluded compilation
from this turn. Its recorded phase is `one_bound_native_capture`. The traceback
was in Inductor metadata construction, through Triton's Intel target discovery
and `arch_parser.c` helper compilation, waiting for the C compiler subprocess.
Compiler/runtime initialization had begun; the planned bound block compile did
not complete. This cancellation is a workflow scope change, not a model or
device failure, and supplies no successful capture claim. Run 02 supersedes
the lifecycle coverage of run 01. Both test sessions are terminal; a final
process scan found no remaining lifecycle-test or C-compiler processes.

## Limits before native deployment

Native pre-run occurs after sampling preparation, model loading, injection,
and allocations, immediately before denoising. Rejection is therefore not a
promise of zero preceding side effects. A foreign callback manually placed
ahead of the guard may execute before rejection; the route still checks the
current execution policy before compiled dispatch.

The new lifecycle guard object is present in callback metadata. **Its interaction
with actual full-graph capture remains unqualified**: prior successful compiled
CPU coverage predates this object, and run 02 intentionally uses a dispatch spy.
Arithmetic, native argument mapping, and compiler options were not changed, but
that does not establish capture compatibility for the new metadata.

Validation overhead is unmeasured: owner/route registries and selected block
state are checked before and after routing. Removal restores dispatch only;
clone parents and the route/guard references can retain compiled state and
module owners. There is no compiler-cache or GPU-memory release claim, and no
global Dynamo reset. Actual native-device placement, numerical equality,
resource use, and performance remain separate deployment gates.
