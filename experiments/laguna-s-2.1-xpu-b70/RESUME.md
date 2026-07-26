# Laguna resume point

## BLOCKED: post-recovery collective health is unmeasured (2026-07-26 correction)

The pre-recovery evidence established a real host fault: model runs hung in
`xpu_worker.init_device`, the untouched record commit hung identically, and
the kernel logged a timed-out job and GuC reset on card 3. However, the tracked
four-rank probe wrapper never launched its Python probe. It asked Python to
open a nonexistent file under its scratch directory instead of the committed
sibling `tools/xccl_collective_probe.py`.

All retained `postreload`, `postflr`, `postshm`, and `ladder-preflight` rank
logs contain only that missing-file error and never reach `import-done`.
Therefore their reported `0/4` counts are harness failures, not collective
results. They cannot show whether the module reload, FLR, or shared-memory
cleanup changed collective health. The current post-recovery collective state
is **unknown**.

The wrapper and ladder are now repaired fail-closed, with CPU-only regression
coverage. Do not perform a bus reset or infer another recovery action from the
invalid runs. A clean reboot remains the conservative operator recovery choice
after the already-issued FLRs, but the broken probe does not prove that it is
required.

Cause and full evidence:
`notes/2026-07-26-topology-explosion-wedged-the-collective-stack.md`.
Probe correction and exact evidence boundary:
`notes/2026-07-26-xccl-probe-harness-correction.md`.
A capture segment ceiling has since landed so the same explosion fails as a
Python error instead of costing a reboot.

## Post-reboot order

1. Width 8 at the record commit `ef334233d` — startup completes, 146/145
   captures, median near 94.920. Confirms the host.
2. Width 8 at current HEAD — same checks; confirms the width parameterization
   is inert in practice, not just in predicate.
3. Width 12 — does the topology land near 146/145, and does it stay exact?
   Still the untested hypothesis. Cheap to fail now.
4. Measure width 12, then go to width 16 / depth 15.

## Where the throughput has to come from

Record: **94.920039** tok/s. Reaching 102 needs **+7.46%**.

- Width 12 / depth 11 measured **+6.9%** emitted per cycle → ~101.5. Necessary,
  not sufficient.
- Width 16 / depth 15 projects **+7.9%** → ~102.4 at unchanged cycle time.
  Clears 102 by 0.4%, which is thin and assumes cycle time is flat in M.
  The drafter config carries `dflash_config.block_size: 16`, so depth 15 sits
  inside the block the drafter was trained for. vLLM never reads that field.
- Width-two tree over a 15-node budget projects **+18.3%** using the measured
  top-2 coverage (72.2% → 84.2%). This is the lever with real margin, and it
  needs tree attention in the verifier.


---

## Earlier resume notes

Single page for picking this lane back up. Written 2026-07-25 after the lane
was paused mid-gate. `CURRENT.md` remains the cross-repository authority;
this file is the lane-local detail it points at.

## One-line status

The record is `94.920039` tok/s. The next lever's component gate has passed.
Its TP4 runtime integration gate has burned four one-shot packets on harness
faults without ever generating a token, and a fifth is prepared and awaiting
adversarial review.

## Record identity — do not disturb

| Field | Value |
| --- | --- |
| Result | **`94.920039` tok/s** conservative lower start; support `95.066548` |
| LocalMaxxing | `cmrzrd4tf001ipa013xpx4kid` (APPROVED) |
| vLLM | `ef334233deabeaeedb607056a2db1c90edb3887c` |
| XPU kernels | `4772f727590c51b72add79350b913d098cf67872` |
| Stack | Exact persistent-attention metadata on validated Breakable M8 PIECEWISE graph, DFlash depth 7, TP4+EP4 |
| Gate | 52/52 bitwise exact vs canonical q=1; cross-leg 39/39; long-next 8/8; rollover 4/4; all `cached_tokens=0` |
| Topology | audited 146/145 segments, captured and replayed exactly once per rank |
| Packet | `data/laguna-s-2.1-m8-persistent-attention-metadata-record-20260725.json` |

Weights: `/mnt/fast-ai/llm-models/laguna-s-2.1/{int4,dflash-int4}` on local
NVMe. The USB copy is backup only.

## Active lever: DFlash context-KV workspace

Laguna's eager context-KV precompute allocates new intermediate tensors on
every proposal cycle, in the draft's six-layer context-KV projection. The
record changes only *target* q2-q8 attention metadata and never touches this
path, so the lane is materially distinct rather than a restatement.

- Selector: `VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1`, default-off, fail-closed.
- Worktree: `/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725`
- Candidate source: `7c38a2022` (branch `experiment/laguna-dflash-persistent-metadata-20260725`)
- Harness/packet commit in this repo: `e9182e125`
- **Component status: exact four-card gate PASSED and promoted.** A separately
  committed, sealed offline audit corrected the projected-V view-offset rule
  and returned `exact_four_card_component_pass`.

Why this lever and not another: the current-stream diagnostic and its source
map found no other honest target-MoE or attention-adjacent candidate. W1
N32/N128, QKV/O occupancy, remote-zero, fused expert transactions, native
shared projections, attention capture, collective capture, and gather variants
are each already negative, terminal, unsafe, or absorbed into the record.

## The blocker, and what each packet taught

Four one-shot packets consumed. Every failure was in the gate harness, not in
the candidate optimization, and every one failed *closed* before a token was
generated. That is the harness working as designed, but it has cost four
identities.

| Packet | Reached | Failure |
| --- | --- | --- |
| `de35c566b` | before vLLM import | frozen `PYTHONPATH` omitted the tracked gate-tools directory; control driver exited `ModuleNotFoundError` |
| `f52f9e8ef` | preflight, no run root | correctly refused an RPC directory left stranded by the first failure; the empty dir was moved recoverably to `tmp/dckvr-b-abandoned-de35c566b-20260725T073546Z` |
| `649f150cf` | **furthest**: model hashing, four-card preflight, full TP4/XCCL target and draft load, PIECEWISE capture | vLLM's `apply_model(function)` identity query rejected function serialization because insecure pickle fallback is deliberately disabled. Cleanup clean: `stop_status=0`, `rpc_archive_status=0`, `worker_status=0`, `idle_status=0` |
| fifth (`e9182e125` / `7c38a2022`) | not yet run | prepared; replaces the pickled-function query with a named, default-off worker RPC returning only rank/world/backend, local/TP rank, XPU identity, and target model class |

Sealed run roots live under
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/`.

## Next action

1. **Adversarial source review of the fifth packet** — harness `e9182e125`,
   candidate `7c38a2022` — against the nine acceptance conditions below. This
   is the gate the note explicitly requires: *"design and tooling only. No
   XPU/model execution is authorized until the committed packet receives
   independent source and adversarial review."*
2. Mint a fresh `O_EXCL|O_NOFOLLOW` one-shot marker.
3. Run the gate. **A failed packet is terminal and must never be reused.**

Preconditions before step 3: all four B70s discoverable and strictly idle; no
existing vLLM/worker/torchrun process; no inherited sensitive runtime
environment; fresh canonical owner-private NVMe run and RPC paths; exact tool,
model, tokenizer, teacher, suite, and native-binary hashes.

## Acceptance conditions

The analyzer may report `bounded_single_request_tp4_integration_exactness_pass`
only if all nine hold:

1. both fresh arms complete exactly one request with zero cached prompt tokens;
2. both final 32-token arrays equal the frozen q=1 teacher prefix;
3. prompt IDs, output IDs, raw text, and finish reason match across arms;
4. every normalized raw proposal/target/rejection event matches across all four ranks;
5. each rank captured the audited graph once and replayed it thereafter;
6. public output tokens after the initial M1 token are an exact prefix of the raw
   M8 emissions; any excluded suffix is confined to the final M8 event, contains
   at most seven IDs, and matches across arms;
7. the candidate arm dynamically witnesses workspace execution and reuse after the
   one-shot request-phase arm, while the control witnesses only the incumbent branch;
8. TP4/XCCL ranks map one-to-one onto the four frozen physical B70 identities;
9. model/source/runtime identities, packet consumption, cleanup, idleness, empty
   worker reports, and the evidence manifest all pass.

Any missing field, fallback, trace mismatch, unexpected process, dirty tree,
device error, graph error, cached prompt state, timing field, or malformed
artifact is a terminal failure.

## What a pass does and does not authorize

A pass authorizes **only the design** of a separate preregistered cold
graph-vs-graph performance crossover using the full realistic suite and
contamination canaries. It does not authorize that crossover, a record claim,
a payload, or a LocalMaxxing submission. The gate deliberately carries no
latency, throughput, tok/s, profiler, or endpoint metric.

## Standing rules

From the campaign standard: never sacrifice quality — every promoted result is
exact target-verified on fresh cold prompts. Never cheat — one active
generation, `cached_tokens=0`, no prefix cache or warmed continuation, full run
identity. Grind the ladder; kill a lever only with a measurement.

## Lane pointers

- Roadmap and lever ladder: [`OPTIMIZATION_ROADMAP.md`](OPTIMIZATION_ROADMAP.md)
- Newest preregistration: [`notes/2026-07-25-dflash-context-kv-tp4-runtime-preregistration.md`](notes/2026-07-25-dflash-context-kv-tp4-runtime-preregistration.md)
- Component pass: [`notes/2026-07-25-dflash-context-kv-workspace-preregistration.md`](notes/2026-07-25-dflash-context-kv-workspace-preregistration.md)
- Record note: [`notes/2026-07-25-m8-persistent-attention-metadata-record.md`](notes/2026-07-25-m8-persistent-attention-metadata-record.md)
- Closed rung: [`notes/2026-07-25-routed-w1-n32-component-failed-stop.md`](notes/2026-07-25-routed-w1-n32-component-failed-stop.md)
