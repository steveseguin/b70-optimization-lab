# Inactive CLIP integration proposal after the guarded CPU proof

2026-09-14. Root ran guarded CPU driver v3 once, PID107471: all six candidate
fixture groups passed, with XPU/CUDA uninitialized, guards intact and exactly
one qualified Comfy import omission. The result is under
`host-embedding-cpu-v3-native-01`. It qualifies the standalone tiny CPU ownership
and gather fixture, not the new adapter or any accelerator behavior.

New source only: `scripts/host_embedding_clip.py` and
`scripts/host_embedding_placement_node.py`. No packet10 source, installed module,
endpoint, device, process or runtime setting was changed. The only executed
integration check was stdlib source/AST inspection.

## CLIP boundary

The factory uses original `comfy.sd.load_clip`, setting `initial_device=cpu`
before construction for both modes, `control` and `host-table`. It refuses an
already-loaded or dynamic result. A per-instance CLIP subclass then carries the
ownership group; the global original CLIP class is never patched. Host-table
mode attaches the frozen CPU-proven candidate before first loading.

`load_model` uses the original estimator expression and passes its unchanged
result as `memory_required`. The explicit patcher list is `[encoder, host]`,
which the pinned native loader reverses so that the CPU owner loads first.
Control passes only its encoder. No forced full load, reserve change, or memory
budget override is supplied. Host-table mode must prove the remaining encoder
fully resident and the CPU owner present in normal loaded-model accounting.

Shared-model CLIP clones retain one ownership group and the candidate's shared
host patcher. Existing encode arithmetic calls the original superclass method.
The adapter counts successful encodes, rejects stale/failed groups and modified
layer/scheduling/hook policies, and retains the original device context.

## State and restoration boundary

Active CLIP get/save/load/patch APIs refuse operations until ownership is
restored. Root `state_dict` hooks also prevent silent omission of the extracted
table. Load-state hooks cover the registered module trees, including the host.
A private ContextVar allowance permits root state reads during the normal
loader's size-accounting path and explicit restoration; reload remains refused.
This assumes the declared static, unmodified component policy and does not
promise protection from arbitrary concurrent monkeypatches or raw tensor writes.

Retirement detaches the encoder, calls the candidate's restore operation (which
also detaches the host), then removes the restored embedding from the retired
host container and resets that patcher's size. The latter integration step is
necessary: the standalone candidate kept its CPU container for inspection after
restoring the original encoder registration. The live loader must not count
that same registered module under two owners. Retirement verifies original byte
counts, all-CPU encoder state, zero host parameters/accounting and retires all
shared CLIP clones. Serialization is permitted after successful restoration;
retired clones cannot resume encoding as an implicit new variant.

## Per-request metadata contract

`LTXHostEmbeddingPlacementCheck(clip, conditioning, run_name, encoder_mode)`
returns the identical CONDITIONING object. It requires exactly one new completed
encoding since its previous receipt and emits exclusive
`host-embedding-placement-{run_name}.json` in the existing dedicated server run
directory. Existing fault/run-name/identity guards are reused. The receipt
contains actual registered encoder and host parameter/buffer inventories,
separate loaded/eligible byte counts, original combined bytes, owner IDs,
inference/version-check scope and the unchanged estimator argument. It does not
copy tensor values or qualify numerical outputs itself.

## Minimal next integration and gates

Prefer a new component-node helper for both modes, with the original five output
ports and one shared component cache/generation. This preserves every packet10
source byte and avoids weakening inherited source-closure checks. Before a mode
change, record both owners, explicitly detach/restore, verify retirement, then
replace the component set. The proposed filenames are
`host_embedding_resident_node.py` and the two prepared helpers above. No such
component node or packet was built in this bounded task.

Before deployment, a scheduled guarded CPU integration proof must exercise the
actual CLIP loader call path, estimator forwarding and owner registration,
shared clones, direct/CLIP serialization refusals, restored complete state,
host retirement, and same-object conditioning passage. Source checks alone
do not establish these runtime properties. Native startup must verify actual
node registration and initial CPU placement before any clip. Then require the
unchanged four raw output oracles, complete per-request placement, and bounded
same-process original/host/original timing with no retries or fault bypasses.

`scripts/check-host-embedding-integration-source.py` passed the stdlib contract:
exact estimator AST, sole unchanged memory_required argument, explicit CPU
initial construction and both-owner inclusion, state API guard presence, and
frozen source/prior CPU-result hashes. Evidence:
`data/host-embedding-integration-source-01.json`. Prepared sources are preserved
in `patches/host-embedding-clip-integration-01.patch`.

Root read the full adapter and placement node after preparation. Before native
qualification, add bounded per-request observations for token-ID shape/device/
dtype and embedding output shape/device/dtype. The current inventory records
parameter placement; it does not establish those dynamic tensor properties.
Keep the frozen tiny-CPU candidate separate from native shape admission.
