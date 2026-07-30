# Laguna DFlash compute-segment graph with eager collectives

Date: 2026-07-30 America/Toronto

Status: **implemented and offline-gated, but not device-executed or endpoint
measured.** The treatment was preregistered before its implementation. The
host's four-rank collective path is currently classified wedged after the
rejected whole-drafter graph route. No reboot is authorized by this note.

## Why this is a new treatment

`VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH=1` is retired. It eventually emitted
all-zero proposals inside a live request, failed the target-teacher gate, and
left a corrected minimal four-rank probe stuck after every rank entered
`all_reduce`. It must remain off.

The rejected wrapper captured the drafter without giving its twelve TP
all-reduces the target path's explicit eager-boundary treatment. A collective
could therefore become part of an XPU graph segment. The target's valid
146/145 graph path does the opposite: every collective writes into a
runner-owned fixed-address buffer and remains eager between captured compute
segments.

The DFlash forward is still the largest measured disproportionate cost:
roughly 9 ms per speculative cycle for six dense layers. The intended treatment
applies the already-proven target design to the drafter while keeping the
unsafe selector disabled.

## Treatment

Add one default-off selector:

```text
VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH=1
```

It is valid only for the sealed BF16-KV width-12/depth-11 TP4 Laguna lane with
the exact target graph, DFlash context-KV workspace, and DFlash FP8 W8A16
projections enabled. The legacy draft-graph selector must be zero.

The candidate:

1. preallocates twelve non-aliasing `[12,3072]` BF16 collective outputs per
   drafter, before any capture;
2. turns each of the six attention calls and twelve TP all-reduces into eager
   boundaries;
3. captures only the stateless compute between those boundaries;
4. requires exactly 19 graph segments and 18 eager breaks per draft forward;
5. requires the same collective slot order, count, shape, dtype, device, and
   output addresses on every replay; and
6. keeps the target's independent audited 146/145 topology unchanged.

No collective is captured or replayed. No target arithmetic, target KV state,
rejection rule, sampling rule, model weight, quantization, prompt, or scoring
window changes.

## Gates and stop rules

Before a model run:

- the legacy draft graph remains explicitly rejected;
- selector-off arithmetic and collective routing remain unchanged, while the
  matched-source control quantifies any residual guard overhead;
- CPU/static tests cover selector exclusivity, the width-12 capture filter, the
  twelve-slot contract, capture-versus-replay accounting, shape drift,
  overflow, aliasing, and output substitution;
- the wrapper and measurement harness both require the 19/18 topology;
- the exact source diff and test-result summary are committed; and
- the host is recovered only after explicit user approval, followed by one
  corrected `PROBE_RESULT=PASS clean_teardowns=4/4` probe.

The first GPU step is a bounded component/model smoke, not the scored suite. It
must prove:

- every graph topology is 19/18 on all four ranks;
- all twelve collectives execute eagerly on every capture and replay;
- proposals remain nonzero and have a normally decaying per-position
  acceptance curve beyond the prior cycle-33 failure boundary;
- the target remains 13/13 bitwise exact on the fixed teacher if an endpoint
  leg is reached; and
- shutdown, worker cleanup, port release, and post-run idle pass.

Any zero proposal row, flat acceptance, missing eager collective, topology
drift, collective hang, or teacher mismatch rejects the route immediately. No
retry, reset ladder, FLR, driver reload, or shared-memory deletion is
authorized by a failed candidate.

Only an exact, cache-zero, topology-valid cold result may be compared with the
current SCALE_VEC incumbent median of `102.134914 tok/s` conventional. The
goal remains 120 tok/s, but this note makes no projected or measured throughput
claim.

## Offline implementation record

The candidate is isolated from the incumbent:

- vLLM base: `d1a72ff78f2db4a51b9c7d84506b201c26d0baae`;
- candidate branch: `experiment/laguna-dflash-segmented-bf16-20260730`;
- candidate commit: `7153f136704b814c5ec02d1a12c40fac2259620f`;
- worktree:
  `/home/steve/src/laguna-vllm-dflash-segmented-bf16-20260730`; and
- preserved patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-segment-Laguna-DFlash-graph-around-eager-collect.patch`
  with SHA-256
  `caea451009909e5eacbda76cd49ad7f53c3e4087af67e5e305b61c547b24563e`.

The reusable measurement leg now has an explicit 26th argument,
`DFLASH_SEGMENTED_GRAPH`, records the selector in `identity.txt` and the
service environment, rejects its combination with the retired whole-draft
graph, requires the complete width-12 FP8-draft stack, and requires one 19/18
capture plus replay record from each TP rank in addition to the target's
independent audited topology.

Offline gates on the committed candidate:

- `64 passed` for the complete DFlash context-workspace/model suite plus the
  new collective-state suite;
- `3 passed` for segmented configuration acceptance, legacy-selector
  rejection, and exact width-12 capture filtering;
- `6 passed` in the focused collective/filter/model-length selection;
- Python `compileall`: pass;
- Ruff on all changed Python and test files: pass;
- measurement-leg `bash -n`: pass;
- Git whitespace checks on the vLLM source diff and measurement harness: pass
  (the preserved mail-format patch is excluded because context lines and its
  `-- ` signature separator are expected to trip `git diff --check` when the
  patch is itself tracked); and
- `shellcheck`: unavailable on this host, recorded rather than implied.

These are offline results only. They prove the contract and fail-closed
plumbing, not XPU graph correctness, throughput, or host recovery.

## Authorized recovery gate

Steve authorized one clean reboot on 2026-07-30. The recovered host reported:

- boot ID `aa094a14-86a2-4615-b0db-7b84d42c7970`;
- boot time `2026-07-30 10:12:28` America/Toronto;
- kernel `7.0.0-28-generic`, taint `0`;
- the expected four B70 BDFs `23:00.0`, `27:00.0`, `43:00.0`, and `47:00.0`;
- four render nodes, no vLLM/probe workers, and no port-18080 listener;
- one bounded changing-value allocation/arithmetic/copy/synchronize pass on
  each physical card; and
- dynamic CCL interface resolution to `eth1`.

Exactly one corrected four-rank collective probe then passed:

```text
PROBE_RESULT=PASS clean_teardowns=4/4
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/
  xccl-postreboot-segmented-2HC3w2/probe-postreboot-segmented
```

Every rank reached `all_reduce-done`, verified the expected sum, destroyed the
process group, and exited zero. No FLR, driver reload, unbind/rebind,
shared-memory deletion, retry, or reset ladder was used. This establishes
post-reboot TP4 collective health; it does not yet establish the segmented
DFlash candidate.
