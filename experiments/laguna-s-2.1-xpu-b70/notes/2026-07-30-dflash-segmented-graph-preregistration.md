# Laguna DFlash compute-segment graph with eager collectives

Date: 2026-07-30 America/Toronto

Status: **first bounded live smoke failed closed during capture; corrected
topology is offline-gated but not yet device-validated or endpoint measured.**
The treatment was preregistered before its implementation. The initial
preregistration incorrectly omitted the vocabulary-parallel embedding
all-reduce; the correction and immutable failed artifact are recorded below.

## Why this is a new treatment

`VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH=1` is retired. It eventually emitted
all-zero proposals inside a live request, failed the target-teacher gate, and
left a corrected minimal four-rank probe stuck after every rank entered
`all_reduce`. It must remain off.

The rejected wrapper captured the drafter without giving its thirteen TP
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

1. preallocates thirteen non-aliasing `[12,3072]` BF16 collective outputs per
   drafter, before any capture;
2. turns each of the six attention calls and thirteen TP all-reduces into eager
   boundaries;
3. captures only the stateless compute between those boundaries;
4. requires exactly 20 graph segments and 19 eager breaks per draft forward;
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
  thirteen-slot contract, capture-versus-replay accounting, shape drift,
  overflow, aliasing, and output substitution;
- the wrapper and measurement harness both require the 20/19 topology;
- the exact source diff and test-result summary are committed; and
- the host is recovered only after explicit user approval, followed by one
  corrected `PROBE_RESULT=PASS clean_teardowns=4/4` probe.

The first GPU step is a bounded component/model smoke, not the scored suite. It
must prove:

- every graph topology is 20/19 on all four ranks;
- all thirteen collectives execute eagerly on every capture and replay;
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
graph, requires the complete width-12 FP8-draft stack, and requires one 20/19
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

## Bounded live-smoke harness

Before the scored suite, the measurement leg's explicit 27th argument can
select a non-scored two-request smoke. It:

- emits exactly 400 tokens from fixed suite rows 0 and 1, crossing the old
  cycle-33 failure boundary and one live request rollover;
- requires each emitted token prefix to equal the canonical q=1 teacher and
  requires `cached_tokens=0`;
- snapshots speculation metrics around each request independently, requiring
  depth 11, more than 33 drafts, neither zero nor flat-full acceptance, and a
  non-increasing curve whose final position is below its first;
- requires target 146/145 and draft 20/19 capture/replay records from all four
  ranks;
- reports `scored_measurement=false` and no throughput; and
- uses the formal leg's graceful shutdown, worker/listener proof, post-stop
  idle interval, artifact sealing, and failure trap.

CPU-only parser/contract tests are `4 passed`; Bash syntax, Python compilation,
Ruff, and whitespace checks pass. This harness exists to reject the candidate
before the 13-prompt score, not to create a smaller or easier benchmark.

## First bounded live smoke: failed closed

The first non-scored smoke ran after the single corrected TP4 recovery probe:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-segmented-smoke-20260730T143735Z
```

It failed during capture before the endpoint became healthy:

```text
RuntimeError: Laguna DFlash graph exceeded its 12 all-reduce slots
```

The harness then completed a graceful four-worker shutdown and formal idle
proof: `stop_status=0`, `worker_status=0`, and `idle_status=0`. This was a
candidate-contract failure, not evidence of another host wedge, so no probe,
reset, FLR, driver reload, shared-memory cleanup, or reboot followed.

The original 12-reduction and 19/18 topology was wrong. Static model inspection
accounts for the observed thirteenth reduction exactly:

- one shared `VocabParallelEmbedding` all-reduce; and
- two all-reduces in each of six DFlash layers (attention output and MLP down
  projection).

Together with six eager attention boundaries, that is 19 eager breaks and 20
compute graph segments. The fail-closed buffer count, wrapper topology,
measurement verifier, smoke verifier, and CPU tests were corrected together.
The failed artifact remains the source of truth for the original attempt; it
must not be relabeled as a device or performance result.

The correction is preserved separately from the initial implementation:

- corrected vLLM commit:
  `4f5e7a63cbd0d0bb409207e079421d0d5532d197`;
- correction patch:
  `patches/laguna-s-2.1-xpu-b70/0002-xpu-account-for-DFlash-embedding-collective.patch`;
- correction patch SHA-256:
  `e42c112ad7b4eeb5b14035db0d76f9e776d947768c18b073d1ca4c19efa98b0c`;
- focused vLLM tests: `9 passed`;
- smoke parser tests: `4 passed`; and
- Python compilation, Ruff, Bash syntax, and Git whitespace checks: pass.

## Corrected-topology smoke: graph pass, harness gate invalid

The corrected source reached the live endpoint in:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-segmented-smoke-20260730T144638Z
```

All four ranks captured and replayed the corrected draft 20/19 topology and
the unchanged target 146/145 topology. Both 128-token requests returned HTTP
200, after which the diagnostic rejected request index 1 because it used no
more than 33 speculative cycles. The service again shut down gracefully and
the formal worker and idle checks passed.

That rejection exposed a harness error, not a candidate error: 128 emitted
tokens cannot guarantee more than 33 cycles when one cycle can emit as many as
12 tokens. The smoke length is therefore corrected to 400 tokens. Since
`400 > 33 * 12`, every complete 400-token response must execute at least 34
cycles even with perfect draft acceptance. The two selected q=1 teacher rows
both contain 512 tokens, so the exact-prefix oracle remains available. This
diagnostic remains non-scored and makes no throughput claim.

## Corrected bounded smoke: pass

The 400-token correction passed:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-segmented-smoke-20260730T145325Z
```

- status: `PASS`, `scored_measurement=false`;
- both fixed q=1 teacher prefixes exact for 400 tokens;
- `cached_tokens=0` for both requests;
- request-local draft cycles: 105 and 62;
- accepted draft tokens: 299/1155 and 338/682;
- both per-position acceptance curves were non-increasing and extended through
  position 10;
- target capture and replay: 146/145 on all four ranks;
- draft capture and replay: 20/19 on all four ranks; and
- graceful shutdown, worker/listener removal, and formal post-idle proof:
  pass.

This validates bounded live correctness and graph replay beyond cycle 33. It
does not establish 13/13 full-suite exactness or throughput. The next permitted
step is one formal scored leg with the same identity and the smoke-only flag
disabled.

## First formal scored leg: exact 119.189 tok/s

The first full-suite leg passed:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-segmented-scored-20260730T150033Z
```

- historical published metric:
  `119.18937096651626 tok/s`;
- preferred 99-interval metric:
  `117.9974772568511 tok/s`;
- 13/13 exact token IDs and response text hashes against q=1;
- all 13 `cached_tokens` values zero;
- one invocation of each fixed unique prompt, no retries or warmup;
- target capture/replay 146/145 and draft capture/replay 20/19 on all four
  ranks; and
- graceful shutdown plus formal post-idle proof: pass.

Relative to the `102.134914 tok/s` incumbent cited at preregistration, the
historical metric is about 16.7% higher. This is one cold leg, not a confirmed
multi-leg median or a 120 tok/s claim. It is 0.811 tok/s below the 120 target.
