# Laguna DFlash context-KV TP4 runtime exactness preregistration

Date: 2026-07-25 America/Toronto

Status: **design and tooling only. No XPU/model execution is authorized until
the committed packet receives independent source and adversarial review.**

## Execution history

The first reviewed packet, main commit
`de35c566b9fa96525bdb864c41989924fd97bd7a`, was consumed once at:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dflash-context-kv-runtime-de35c566b-94de2d07a-20260725T073546Z`

It failed closed before importing vLLM, loading a model, or generating any
token. `PYTHONSAFEPATH=1` correctly removed the script directory from implicit
module search, but the frozen `PYTHONPATH` omitted the tracked gate-tools
directory required for importing the raw analyzer. The control driver exited
with `ModuleNotFoundError`; candidate did not start. Failure cleanup found no
workers, all devices idle, and sealed the root with
`failure-manifest.sha256`. That consumed packet is terminal and will not be
reused.

The revised packet explicitly freezes the tracked tools directory first in
`PYTHONPATH`. It requires a new commit, independent review, and a new one-shot
marker before execution.

The revised `f52f9e8ef559f80de9a34857d501335f4daebeda` packet was invoked
once, but stopped in preflight before creating a run root or consuming its
marker. The first failure had created both fixed RPC directories up front and
archived only the active control directory, leaving an empty candidate RPC
directory. The second invocation correctly refused that reused path. The empty
directory was moved recoverably to
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/dckvr-b-abandoned-de35c566b-20260725T073546Z`.

The runner is revised again to create an arm's RPC directory only immediately
before that arm and to bind it into active cleanup before worker and idle
checks. A control failure can therefore no longer strand a precreated
candidate RPC directory. RPC archival must itself succeed before active state
is cleared; failure cleanup records `rpc_archive_status` and preserves the
source path for recovery. This change also requires a new commit and review.

The reviewed `649f150cfe858388587fa3ad384d7004a2c490dd` packet passed
model hashing, four-card preflight, full TP4/XCCL target and draft load, and
PIECEWISE graph capture. It then failed before its only chat-generation call:
vLLM's `apply_model(function)` identity query rejected function serialization
because insecure pickle fallback was intentionally disabled. Candidate did
not start. Cleanup reported `stop_status=0`, `rpc_archive_status=0`,
`worker_status=0`, and `idle_status=0`; the root is sealed at:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dflash-context-kv-runtime-649f150cf-94de2d07a-20260725T074226Z`

The candidate source is revised with a named, default-off XPU worker RPC. The
method is callable only while both the frozen lifecycle trace and raw evidence
contracts are active, accepts no serialized function, and returns only
rank/world/backend, local/TP rank, current XPU identity, and target model
class. The driver calls that named RPC through the ordinary safe control
message path. Insecure serialization remains disabled. This source and packet
require new commits and independent review.

The reviewed `93167cf4972400cf0f1316b210bf760566004909` packet then
completed its sole 32-token control generation and produced 72 lifecycle files
plus the complete raw recorder stream. It failed while writing `driver.json`:
the vLLM constructor had mutated one of the caller-owned configuration
dictionaries in place to contain a non-JSON `ModelConfig`. The driver was
recording that mutated object instead of the primitive launch contract.
Candidate did not start. Cleanup again reported zero stop, RPC-archive, worker,
and idle failures. The root is sealed at:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dflash-context-kv-runtime-93167cf49-7c38a2022-20260725T080004Z`

The driver is revised to create immutable JSON snapshots of engine,
compilation, and speculative configuration before constructing `LLM`, and to
record only those launch snapshots. Runtime mutation therefore cannot corrupt
the result schema. This requires another committed and reviewed packet.

The reviewed `fc6580d381d733e680c67297925490c78f263afc` packet
successfully completed and cleaned up both 32-token arms. Both final driver
records, all 144 lifecycle events, both raw streams, post-arm idle proofs, and
the evidence manifest were written. The final analyzer rejected the first
control lifecycle event because its initial draft-profile context width is
C8192, while the analyzer incorrectly allowed only C1-C8 for every lifecycle
event. The sealed traces show the actual deterministic sequence on every rank:

- initialization/profile: C8192 incumbent, then C8/C8/C1;
- request prefill: C90 incumbent with six expected cache updates;
- request DFlash cycles: repeated C8 with six expected cache updates;
- selector-on uses the workspace exactly for eligible C1-C8 calls and the
  incumbent path for C90/C8192, matching the frozen source contract.

The root and both successful arm cleanups are sealed at:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dflash-context-kv-runtime-fc6580d38-7c38a2022-20260725T081640Z`

The analyzer is revised to validate any positive lifecycle width through the
frozen 8192-token model limit, require the incumbent branch above C8, and
require workspace geometry/reuse only for selector-on C1-C8 events. Acceptance
still requires an eligible request-phase workspace reuse on every rank. This
analyzer repair requires a new committed and reviewed packet; the sealed
fc658 evidence is not retroactively promoted.

Direct replay of the repaired lifecycle validator against that sealed root
then exposed a second analyzer-only fixture error before any rerun: the
workspace was validated with the target model's six local KV heads instead of
the DFlash draft model's two local KV heads. The frozen candidate source and
sealed rank traces both establish the actual TP4 geometry as K/V width 512,
`all_kv` shape `[2, 6, C, 2, 128]`, and normalized-K shape
`[6, C, 2, 128]`. The analyzer and its fixtures now require that exact draft
geometry. This correction also requires a newly committed and reviewed packet;
no prior sealed evidence is promoted.

## Question

Does the default-off DFlash context-KV workspace preserve the approved Laguna
S 2.1 TP4+EP4 DFlash7 runtime exactly when exercised through the real loaded
model, speculative proposer, target verifier, rejection sampler, and KV-cache
lifecycle?

This is an integration-correctness gate. It is not a performance experiment.

## Frozen source and model identity

- candidate vLLM:
  `/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725`,
  `7c38a20229b7bcd0f149e3e9a6b6b5493c3bd85b`;
- XPU kernels:
  `/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727`,
  `4772f727590c51b72add79350b913d098cf67872`;
- target:
  `/mnt/fast-ai/llm-models/laguna-s-2.1/int4`,
  revision `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash draft:
  `/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4`,
  revision `5e07c246915c86dc6920fead03d019989224f2ba`;
- active artifacts, private state, RPC paths, and evidence must remain on the
  internal NVMe/ext4 filesystem under `/mnt/fast-ai`;
- the external Corsair/USB volume is backup-only and forbidden for this gate.

The candidate is a direct descendant of approved record vLLM `ef334233d`.
The approved LocalMaxxing record remains `cmrzrd4tf001ipa013xpx4kid` at
`94.92003934159611 tok/s`. Nothing in this gate can replace or modify it.

## Two-arm treatment

Run exactly two separately launched offline `LLM.chat` processes, in this
order:

1. `control`: `VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=0`;
2. `candidate`: `VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1`.

Both arms use the approved TP4+EP4, DFlash7, BF16-KV, synchronous,
one-active-sequence, Breakable PIECEWISE graph stack with persistent exact
attention metadata. Both use the existing default-off
`VLLM_XPU_LAGUNA_M8_EVIDENCE=1` raw recorder in `segmented-graph` mode. The
workspace selector is the sole treatment difference.

Each arm gets a new process, private home/cache/temp state, fresh RPC root,
fresh recorder root, and exactly one chat-generation call. There is no warmup,
retry, second request, endpoint, or reused model/cache state.

## Frozen request

Use the first prompt in `realistic-suite-v1.json`, `python-lru-cache`, through
the model's normal chat template with `enable_thinking=false`.

- temperature: `0`;
- top-p: `1`;
- seed: `1`;
- max output: `32`;
- ignore EOS: `true`;
- prefix caching: disabled;
- async scheduling: disabled;
- max active sequences: `1`.

Thirty-two tokens are intentionally sufficient to produce several real
DFlash proposal/verification cycles while keeping synchronous raw evidence
bounded. The output token array must equal the first 32 tokens of the frozen
canonical q=1 teacher row. This packet does not replace the later 13-prompt,
512-token cold performance-quality gate.

## Required evidence

For both arms and all four ranks, revalidate the existing raw recorder files
and compare every eligible target event. Equality includes:

- candidate/draft token IDs entering target verification;
- target sampled token IDs;
- accepted draft prefix length;
- first rejected draft index;
- emitted IDs before and after scheduler bookkeeping;
- target hidden boundary;
- all 48 target attention inputs/outputs observed by the existing recorder;
- live slot-routing identities;
- audited graph capture/replay topology and collective outputs.

Also require exact control/candidate equality for prompt token IDs, final
token IDs, raw output text, finish reason, and cache count. Both final token
arrays must independently equal the canonical q=1 teacher prefix.

The frozen candidate contains a default-off, non-timing lifecycle witness
inside the actual DFlash projection path. It records the selected incumbent or
workspace branch, C width, stable workspace geometry/reuse within a rank, input
and slot-mapping signatures, and completion only after the inherited DFlash
precompute method returns. The analyzer requires a fully mapped six-layer
precompute return and at least one real same-width workspace reuse on every
rank after an explicit request-phase arm. Initialization/profile lifecycle
events are retained and compared but cannot satisfy request-path acceptance.
Immediately before the sole chat call, the driver invokes a second named,
one-shot worker RPC that arms the phase independently on ranks 0-3. The
lifecycle phase may transition only from unarmed to armed.

The candidate's bounded workspace execution is established jointly by:

- the selector-on process environment;
- the in-model lifecycle witness on all four ranks;
- a valid real DFlash proposal/verification event stream on every rank;
- the frozen source branch that uses the workspace for `0 < num_ctx <= 8`;
- the separately promoted four-card component proof for every width C1-C8.

No pointer equality is required between arms. The treatment deliberately
changes temporary allocation lifetime.

The recorder does not capture physical KV-cache bytes. This gate therefore
does not claim physical cache-byte equality or exhaustive KV-lifecycle
equivalence. Its claim is limited to observed branch execution, a successful
fully mapped inherited precompute return, exact observed speculative/target
trace equality, and the exact public output prefix.

## Fail-closed operational contract

Before the one-shot marker is consumed, require:

- clean main, vLLM, and kernel worktrees at their recorded commits;
- exact tool, model, tokenizer, teacher, suite, and native-binary hashes;
- all four physical B70s discoverable and strictly idle;
- no existing vLLM server, worker, or torchrun process;
- no inherited sensitive runtime environment;
- fresh canonical owner-private NVMe run/RPC paths.

The committed packet identity is consumed once with an external
`O_EXCL|O_NOFOLLOW` marker. A failed packet is terminal and must not be reused.
All raw files and the final manifest are sealed read-only after success or
failure.

## Acceptance

The analyzer may report
`bounded_single_request_tp4_integration_exactness_pass` only if:

1. both fresh arms complete exactly one request with zero cached prompt tokens;
2. both final 32-token arrays equal the frozen q=1 teacher prefix;
3. prompt IDs, output IDs, raw text, and finish reason match across arms;
4. every normalized raw proposal/target/rejection event matches across
   all four ranks;
5. each rank captured the audited graph once and replayed it thereafter;
6. public output tokens after the initial M1 token are an exact prefix of the
   raw M8 emissions; any excluded suffix is confined to the final M8 event,
   contains at most seven IDs, and matches across arms;
7. the candidate arm dynamically witnesses workspace execution and reuse,
   after the one-shot request-phase arm, while the control witnesses only the
   incumbent branch;
8. TP4/XCCL ranks map one-to-one onto the four frozen physical B70 identities;
9. model/source/runtime identities, packet consumption, cleanup, idleness,
   empty worker reports, and the evidence manifest
   pass.

Any missing field, fallback, trace mismatch, unexpected process, dirty tree,
device error, graph error, cached prompt state, timing field, or malformed
artifact is a terminal failure.

## Explicit exclusions and next authority

Operational logs may contain ordinary process metadata, but the model records
and analysis contain no model latency, throughput, tok/s, profiler output,
endpoint metric, or LocalMaxxing payload. A pass authorizes only the design of
a separate preregistered cold graph-vs-graph performance crossover using the
full realistic suite and contamination canaries. It does not authorize that
crossover, a record claim, or a submission by itself.
