# Packet58vb launch repair — 2026-10-18

The coordinator's smoke attempt at 16:23:22 UTC refused before device work:
the inherited gate admitted `screen-packet58r-*`, while lanequeue created
`screen-packet58v-smoke-A.service`. No model window or device output directory
exists. The reported fault count was two; this repair launches nothing.

The gate now accepts the packet58v lanequeue prefix and the existing
`packet58-` coordinator prefix. `launch_identity.py` calls lanequeue's actual
`command()` builder to derive names. It does not duplicate `screen-` naming.
The seal binds lanequeue's source as well as the local helper.

## Literal sweep

Reviewed all packet Python, native/header code, identity/configuration files,
source seals and proposal paths, including queue_runner, window, suite_driver,
compare_bracket, views, native argument assembly, admission and teardown.
Search: `rg -n '58[rptn]|packet[0-9]+[a-z]?|card0-|screen-'` over these files.

| Finding | Disposition |
| --- | --- |
| `screen-packet58r-` unit gate | Replaced by the lanequeue-derived packet58v prefix; unrelated packets refuse. |
| `packet58r.plan.v1`, `packet58n.arm.v1` | Corrected to packet58v receipt labels. |
| `packet58r build` diagnostic | Corrected to packet58v. |
| `packet58p-arguments-`, test `card0-loo-a` | Corrected CPU scratch labels. |
| Historical measurement accidentally pointed at packet58v's nonexistent `card0-v5-a` | Restored packet58r receipt/source paths; regenerated measurement is byte-identical. |
| `--p58r-parse-test` in native_source/startup_gate | Retained existing CPU-only parser ABI in the unchanged binaries; neither proposed device command uses it. |
| 58p/58r/58t measurement paths, library-path provenance, copy-manifest and source pins | Retained exact historical inputs, not new output destinations. |
| packet58u host-admission schema and parent data | Retained the sealed measured admission policy; no policy or reserve reduction. |
| packet49 selection/oracle, packet56 metrics/supervision, packet58j objects, packet98c bracket lineage | Retained actual shared dependencies and arithmetic identities. |
| Shared `own-runtime.packet58.*` schemas and chain-lanes/drain protocol names | Retained compatibility contracts, not packet-specific output names. |

Both output destinations remain under this packet's `evidence/card0-async-a`.
No frozen tree, shared ops implementation or live queue was edited.

## CPU evidence and limits

`argument_gate.py` now starts with each proposal's actual `queue_runner.main`
arguments and lanequeue-derived `/proc/self/cgroup` content. For both jobs it
continues through K1a, K1b and WSCREEN's real window/suite entry points,
unit/environment gates, passive sysfs topology admission, live `/proc/meminfo`
admission, K1 selection, oracle inputs and native argument assembly. Execution
is intercepted immediately before native launch; audit hooks forbid subprocess
execution, device/model opens and writes outside scratch.

The old gate is extracted from `ba0dc6e7b` and substituted into the same real
queue entry: both jobs refuse at that gate. The fixed gate reaches all six
native boundaries. Four additional unit tests accept both proposed services
and coordinator chains and reject parent packets, system services, scopes,
nested groups and similarly named unrelated packets. All **91** Python policy
tests pass. The six launch records include topology, host admission, inherited
resource limits and proposal hashes in [argument-gate.json](evidence/argument-gate.json).

Coordination locks, prior device receipts, journal review, placement observations,
ldd, client ownership and the memory fence are isolated test boundaries. The
build envelope is synthetic during replay to avoid circular sealing; actual
source, binary and gate hashes are verified separately by `seal.py --verify`.
The test does not grant device authorization or prove async device equality.
Live device startup must still repeat all operational checks and the v5 job
still requires the exact smoke's output and clean drain.

No compiler or native build was run. The minimal reseal retains every binary,
native source, arithmetic identity (`iq3-p49-split32-v1`), oracle, full BF16 KV,
host reserve and device bound. See [minimal-reseal.json](evidence/minimal-reseal.json).
Both proposals pass lanequeue planning on temporary queues and remain unqueued.

The final readiness file binds the committed repair and exact proposal hashes.
It is written after the repair commit and is the last task content write; its
own follow-up commit avoids an impossible self-referential commit hash.

Revisit this launch repair only if coordinator naming or startup wiring changes.
The next device work is the unchanged mandatory smoke, then v5 only on success.
