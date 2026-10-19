# Packet165: warm-runtime, cold-prompt 512-token prefill

CPU preparation only. Warm 512-token prefill is **not measured yet**. This
packet contains copies of packet163's one- and two-card harnesses, with the
first suite request moved ahead of prefill. Existing packet trees, shared
operations code, live queues and services are unchanged.

Each fresh owner loads the same model once and runs:

1. `incident-retrospective`, the first registered suite prompt, **once** with the
   unchanged 512-token response cap. This is the distinct warm-up request.
2. A full request-state reset, then the unchanged 512-input-token prose prompt.
3. The remaining eleven registered suite prompts, each once after a full reset.

The warm-up remains in the twelve-prompt suite report, with its actual cold
first-request cost. It is never repeated or discarded. The measured 512-token
prompt has not previously run in that process. All thirteen input token arrays
must differ. Every available packet49 oracle token is checked, including the
warm-up. There is no prompt, KV, response, n-gram or history reuse.

The prefill receipt requires exactly one completed preceding request, records
its prompt and receipt hashes, and binds the full-reset receipt hashes. It
asserts `cached_tokens=0`. Two-card zero-cache evidence comes from both native
full-allocation resets; one-card also checks the native cache-zero field.
Immutable weights, resident weight lookups, allocated buffers and compiled
kernels may remain resident. Request state cannot.

## Measurement definition

The primary prefill figure is **512 / request TTFT seconds**, one user: native
`request_start_monotonic` through the first generated token's
`completed_monotonic`. It includes host/controller and first-token work and
excludes model loading. This is not HTTP TTFT.

| Topology | Existing request-start boundary, retained unchanged |
| --- | --- |
| One card | Immediately before native request reset; TTFT **includes reset**. |
| Two cards | After both ranks' full request reset; TTFT **excludes reset**. |

The report separately preserves the parent's native prompt-loop wall time and
its 512/time rate. That loop runs through the first generated token, including
the final prompt position and output head; it excludes reset. Neither clock is
device-only time. `prefill_phase_device_ms` is explicitly `null`/not available
because the unchanged token-timing build does not provide an isolated device
prefill phase. Zero GPU counters or host `busy_ms` are not substitutes.

The realistic decode metric, full completion accounting, natural EOS, response
cap, prompt bytes, token IDs, target weights, selection, dispatch, context4096,
BF16 KV and `iq3-p49-split32-v1` arithmetic remain unchanged. Reports select
prefill by prompt ID and reconstruct the twelve suite rows in registered order.

The packet49 oracle still covers only 128 output tokens. Longer outputs remain
**fresh-process determinism only**, not oracle-exact, after matching both loads.
Independent full-output quality and publication gates remain unfinished. This
packet authorizes no submission or performance headline by itself.

## Queue proposals and isolation

Real proposal rows (not inserted into any live queue):

- [Two-card A](../../ops/lane-queue/proposed-p165-two-card-A.txt), two fresh
  loads; whole-host reservation.
- [Two-card B](../../ops/lane-queue/proposed-p165-two-card-B.txt), two fresh
  loads; whole host empty at entry, lane A must remain idle during the run.
- [One-card A](../../ops/lane-queue/proposed-p165-one-card-A.txt), two fresh
  loads; whole-host reservation.

Choose **A or B** for the two-card experiment, not both alternatives. The
second row references the first fresh output and compares every emitted token
of all thirteen requests. Output directories are fresh `device-warm512-*`
paths. Nothing was queued or launched during preparation.

The device free-space floor is **25 GB**; CPU preparation stops below 27 GB.
Unchanged packet163 budgets reserve 1,222,788,768 bytes per two-card load and
57,141,252 per one-card load. Those are conservative estimates, not measured
packet165 writes; the request count and caps have not grown. Every load checks
space separately. Native wait600s/controller1200s and graceful shutdown remain
unchanged. Stream proof has no wall-clock deadline. In-run checks concern
stream presence/format, reset/cache identity, termination and exactness only;
analysis happens after devices drain.

## CPU evidence and rebuild

The queue pin guard initially refused external embedded constant paths. The
private native copies therefore relocate only absolute include/constant paths
from packet163 to packet165. Every kernel object is reused byte-for-byte;
inverse source comparison proves that the entry source has no semantic delta.
The binaries are relinked and have new hashes. See each topology's
`evidence/build.json`, `evidence/identity-check.json` and
`lineage/packet165-build.json`. This is a local lab packet, not a public recipe.

`localize_native.py one-card` / `two-card` reconstruct those entry builds from
the frozen packet163 build inputs and exact objects. It takes the shared
`ops/compile_turn.py` turn. Run CPU tools as
`nice -n 19 taskset -c 8-15,24-31 python3 -B`, with stdin `/dev/null`.
No model tensors are needed. Build outputs and synthetic native-probe scratch
are ignored. CPU compile/probe peak memory must stay below 4 GB.

Two private 4 MiB rotary tables are intentionally retained with the copied
source trees: the queue requires private constant dependencies. Restore each
from the corresponding frozen packet163 `runtime-constants.json` local file
and verify SHA256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
The copies are identity constants, not model tensors or duplicate run logs.

Checks include the real Python arm sequence, production native reset/preparation
paths on CPU transports, sensor survival through every reset, actual argv
against built `--help`, device-path imports without device access, lanequeue
plans and `rehearse_entry --report`. The native probes use synthetic/opaque
weights and Landlock to deny GPU/model access. They do not validate device
arithmetic. The draft reset method is tested separately on a synthetic facade;
its real model constructor is not run.

[The real-evidence replay](evidence/packet163-replay.json) reproduces
58.6097358073 and 58.6252334250 tok/s from packet163's two full512 runs and
keeps those runs' prefill cold. Synthetic 512 tests cover report writing,
warm-up/reset proof, cache refusal, malformed streams, oracle mismatch and
fresh-load mismatch. Shared report fixtures are64/128 and must remain
strict512=false. Shared preparation-schema warnings, if present, are retained;
the independent native gate is required rather than treating a warning as PASS.

READY markers are written **last**, after every final CPU gate, proposal and
file seal. Consult those markers for the completed gate state; this README
alone is not readiness evidence.

The [batched-prefill study](BATCHED-PREFILL.md) gives source lines, existing M=2
building blocks, exactness constraints, a conditional priced ceiling and the
smallest-first build plan. See the [work note](../../../../notes/2026-10-19-own-runtime-packet165.md).
