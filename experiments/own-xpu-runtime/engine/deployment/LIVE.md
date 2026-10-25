# Portable live MTP research recipe

`portable_live.py` connects the authenticated SC117 deployment profile to the
same live MTP wire protocol and scheduler used by the pipeline research lane.
It uses existing official draft weights. It performs no training, installation,
service changes, device resets or automatic restart/retry.

This research recipe now has a bounded four-card live-MTP proof from the
separately extracted `9d6320c1b` source snapshot, using generated local model
configuration. All 32 output tokens, 2,065 target buffers, 73 draft allocations
and 117 true-pair inputs match accepted replay. See the
[portable live proof](../../research/continuation-2026-10-25/portable-live/pp4-proof/RESULT.md).
This qualifies that exact build and recipe on the lab host, not a newer build,
portable speed, clean-host installation or a chat service. The newer rolling
scheduler has a separate lab proof and is not this portable adapter. A new live
deployment must repeat its target/draft and handoff checks. The existing
CPU-reference discrepancy remains outside this recipe's scope.

## Inputs and source closure

Follow [README.md](README.md) to authenticate the target **and official draft**,
optionally the tokenizer, using the pinned profile and independent digest. Keep
that verified deployment's `binding.json` and generated header. No repeated full
model authentication is needed merely to rebuild unchanged sources at the same
verified model locations; the planner checks the exact local file identities.
A moved or changed model requires a newly authenticated binding.

Build this source revision with the generated header, using the profile/binding
SHA256 arguments documented in README.md. An older target-only executable does
not gain live MTP from a Python flag: its build receipt must contain
`pipeline/layout.hpp`, `pipeline/wavefront.hpp`, `pipeline/checkpoint.hpp` and
`pipeline/live_draft.hpp`. Optional draft checkpoint partitioning additionally
requires `pipeline/operator_state.hpp`. The receipt must identify this exact
local generated authority and its compiled dependency, executable and RoPE asset.
Keep the source tree, deployment and runtime libraries available at their recorded
locations for the lifetime of the engine.

The deterministic source exporter now includes these shared protocol modules:

- `tools/pipeline_driver.py`, `wavefront_driver.py`, `live_wavefront_driver.py`;
- the lazy dependency `tools/persistent_live_suite.py` and its CLI
  `persistent_wavefront_driver.py`;
- `planning/wavefront.py` and `live_draft.py`, loaded relative to the package.

It checks tracked committed inputs, native include closure and literal Python
import closure. Untracked/missing runtime modules fail export. The shared tools
also contain historical lab launch functions, but this adapter calls none of
those planners, guards, observers or lifecycle functions. Only `LiveStage` and
`live.drive` are reused; the portable observer and admission guard are injected.
The packaged persistent CLI remains a lab research interface, not a portable
service. Source inclusion alone does not certify every historical entrypoint.

## Create a CPU-only live plan

Write a configuration such as the following, replacing paths, local receipt
hashes and device mappings with the actual verified deployment. The profile hash
is the existing trusted SC117 profile; the local binding/build hashes are distinct.
Runtime library directories must be explicit, unique and canonical. Use the
installed toolchain/runtime directories that were qualified for the new build;
there is no inherited `LD_PRELOAD`, diagnostic environment or shell setup script.

```json
{
  "schema": "ownrt.portable-live-config.v1",
  "deployment": "/path/to/sc117-deployment",
  "profile_sha256": "369ea09fc13015721df09a02841d5ef368d24455f25957d8fc2187e07a96999a",
  "binding_sha256": "REPLACE_WITH_VERIFIED_LOCAL_BINDING_SHA256",
  "build_receipt": "/path/to/generated-build/build-receipt.json",
  "build_receipt_sha256": "REPLACE_WITH_RECORDED_BUILD_RECEIPT_SHA256",
  "bdfs": ["0000:23:00.0", "0000:47:00.0"],
  "library_dirs": ["/opt/intel/oneapi/compiler/2026.0/lib"],
  "output": "/path/to/new/live-run",
  "prompt_tokens": [1, 2, 3],
  "max_new": 32,
  "seconds": 1800,
  "verify_restore": true,
  "draft_partition": false,
  "use_proposals": true
}
```

Native generation capacity is build-versioned. Earlier live binaries accept at
most 128 tokens even though the model profile/planner's upper bound is 512; a
retained full-suite attempt refused 512 before device access. The newer parser
permits up to 512 only for explicitly configured pipeline mode and preserves
128 for legacy entrypoints. The adapter's source-file capability check establishes
that live-MTP code was compiled, not which numerical cap that binary accepts.
Keep the exact qualified build receipt/version in the plan. Use the default
32-token replay for initial portable live qualification; use a 512-token request
only with the newer parser and its separately checked build. Do not infer that
an old executable gained the new cap from a Python plan.

The prompt IDs are only a structural example; use the exact frozen prompt IDs
from the intended reference. `max_new` is bounded at 512 and prompt plus generated
inputs must fit the native context 4,096. Two or four distinct BDFs select the
existing contiguous placements. This profile does not claim a one-card memory
fit or a qualified six-card SC117 deployment.

```bash
python3 "$ENGINE/deployment/portable_live.py" plan \
  --config /path/to/live-config.json --plan /path/to/new/live-plan.json
```

The plan binds the profile, local target/draft identities, generated build,
source helpers, launch policy, command/environment, both EOS IDs and runtime
RoPE asset. It strips the legacy depth-probe variables required absent by native
live mode. Only the first stage owns the existing draft. Each stage has its own
IPC region; the legacy two-rank shared-pair protocol is not used.

`verify_restore=true` enables byte verification of aborted speculative state.
Keep it on for qualification. Changing it or `draft_partition` changes run
identity and requires a new plan/admission. `use_proposals=false` still advances
the same canonical draft true pairs but disables speculative target proposals,
providing a comparison lane. Nothing here asserts a measured speed benefit.

## Check, then explicitly admit one replay

The check command regenerates the plan and verifies independent trust anchors
without launching workers or opening GPUs:

```bash
python3 "$ENGINE/deployment/portable_live.py" check \
  --plan /path/to/live-plan.json --plan-sha256 "$PLAN_SHA" \
  --profile-sha256 "$PROFILE_SHA" --binding-sha256 "$BINDING_SHA" \
  --build-receipt-sha256 "$RECEIPT_SHA"
```

Execution uses the same portable admission schema described in README.md:
`ownrt.portable-run-admission.v1`, owner authorization, plan SHA, reviewed baseline
and SHA, expiry, resource floors, `controller_sha256` for `deployment/controller.py`
and `observer_sha256` for `deployment/observer.py`. It additionally requires
`live_controller_sha256` for `deployment/portable_live.py`. No profile or plan by
itself authorizes device execution.

Select the explicit root, noninteractive `sudo-n`, or independently pinned local
wrapper backend. Missing privilege to inventory other users' GPU descriptors
fails closed. The portable package contains no credential path or password broker.
A wrapper receives exactly the packaged observer script as its sole argument;
its path/hash belong to local admission, not the immutable model profile.

Only after the current physical/fault/resource preflight is accepted, run once:

```bash
nice -n 19 python3 "$ENGINE/deployment/portable_live.py" run \
  --plan /path/to/live-plan.json --plan-sha256 "$PLAN_SHA" \
  --profile-sha256 "$PROFILE_SHA" --binding-sha256 "$BINDING_SHA" \
  --build-receipt-sha256 "$RECEIPT_SHA" \
  --admission /path/to/live-admission.json --unit OWN_CONTROLLING_UNIT
```

The named unit must actually own this process with matching invocation/PID and
`Restart=no`, `KillMode=process`, `SendSIGKILL=no`. Alternatively provide an
inherited `--coordinator-stop-fd`. The adapter does not create a service or unit.
It checks nice level 19, preserves the pinned `ionice -c 3` native wrapper,
loads each stage once, and monitors boot/PCI identity, complete physical holders,
known kernel faults and memory/storage floors. On failure it stops new requests,
signals cooperative stop once, and reports any surviving processes. It never
kills/restarts the engine or modifies host power/memory settings.

A successful replay writes output IDs and scheduler/true-pair traces, a final
full target state for each stage, canonical draft state on the first stage,
preflight/postflight evidence and process exit status. Those artifacts enable
qualification; a clean process exit is not itself a correctness or speed claim.
The current one-shot adapter does not serve chat or run the twelve-prompt suite.

CPU validation (no models or GPUs):

```bash
python3 -m unittest discover -s "$ENGINE/deployment" -p 'test_*.py'
python3 -m unittest discover -s "$ENGINE/release" -p 'test_*.py'
```
