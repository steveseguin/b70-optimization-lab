# Laguna DFlash context-KV TP4 runtime exactness preregistration

Date: 2026-07-25 America/Toronto

Status: **design and tooling only. No XPU/model execution is authorized until
the committed packet receives independent source and adversarial review.**

## Question

Does the default-off DFlash context-KV workspace preserve the approved Laguna
S 2.1 TP4+EP4 DFlash7 runtime exactly when exercised through the real loaded
model, speculative proposer, target verifier, rejection sampler, and KV-cache
lifecycle?

This is an integration-correctness gate. It is not a performance experiment.

## Frozen source and model identity

- candidate vLLM:
  `/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725`,
  `94de2d07a40c64f91f52b17654a1f287ef7b3359`;
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
rank.

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
   while the control witnesses only the incumbent branch;
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
