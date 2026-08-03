# Laguna S 2.1 resume point

Last updated: 2026-08-03 America/Toronto

## Status

The original result is published, approved, sealed, and reproducible. Later
segmented-DFlash, decode-GRF128, transposed scales, and Q/K RMSNorm plus NeoX
RoPE raised the conventional record to `124.64241272122038 tok/s`. The current
treatment adds exact width-12 shared-expert SiLU/multiply and
routed-scale/add fusions and passed its first formally valid cold suite at
**`125.4619731637751 tok/s`** conventional. Its historical compatibility value
is **`126.72926582199506 tok/s`**. It is 13/13 exact and cache-zero with the
frozen 146/145 target, 14/13 draft topology, and four-rank selector evidence.
A later metric
audit found that the published helper used an inclusive-event numerator over
an inter-event span, so the 102 tok/s objective is complete only under that
historical convention, not under conventional interval accounting.

- published legacy-convention result: **`102.97143559613157 tok/s`**;
- conventional 99-interval result: **`101.94172124017027 tok/s`**;
- objective: `102 tok/s`;
- conventional margin: `-0.05827875982973 tok/s`;
- LocalMaxxing: `cms2ccv2d00lps201rej94pjy` (`APPROVED`);
- confirmed M12 shared-elementwise record: **`125.4619731637751 tok/s`** conventional;
- LocalMaxxing: `cms9wuuf300cqpm01t5i285tq` (`APPROVED`);
- lane state: active optimization, no service or worker currently running.

### 2026-08-03 real-use latency and upstream checkpoint

The immediate product objective is now client-visible latency: prompt
processing, TTFT, full request wall time, and long-context decode, while
protecting the `125.4619731637751 tok/s` conventional short-decode record.
The strongest measured treatment already exists: exact pure-prefill chunks
improved 256-token prefill `19.875 -> 184.598 tok/s` and TTFT
`12.883 -> 1.399 s`, while 32K decode remained effectively flat
(`39.589 -> 39.754 tok/s`). It has been combined offline with the INT4
tile-record integration at vLLM `f9e167ad0`; 36 host tests pass.

Community/fork vLLM `main` is synchronized to upstream `5df9999fc`, having been
fast-forwarded from `68ca6fd02`, and the focused public packer branch is
current at `b23676262`. Measured Laguna
branches remain pinned evidence rather than being rebased across roughly 763
upstream commits. Full policy, metrics, and successor ordering are in
[`2026-08-03-e2e-latency-upstream-sync.md`](notes/2026-08-03-e2e-latency-upstream-sync.md).
This is offline progress only; the NVMe/device quarantine still prohibits a
model, endpoint, XPU probe, benchmark, or recovery action.

The first tail follow-up is also complete offline. vLLM `015fee586` extends
the authenticated pure-prefill marker to widths 2--512 and decomposes MoE
tails into exact M12/M8 chunks plus the minimum scalar remainder, without
changing the scheduler partition. This directly targets the incumbent
8K/16K/24K tails of 10/20/30 rows. The combined suite passes 56 host tests,
but raw XPU and endpoint exactness remain unmeasured. See
[`2026-08-03-exact-prefill-tail-offline.md`](notes/2026-08-03-exact-prefill-tail-offline.md).

Production first-user latency is now handled separately from cold measurement.
vLLM `d9e7e2f1a` adds a v2 worker contract that proves the exact-prefill
selector is active, and a default-off production readiness canary runs one
exact 400-token request before publishing an atomic ready marker. It validates
worker/DSO identity, cache-zero response exactness, speculative counters, and
146/145 target plus 14/13 draft capture/replay on all ranks. Cold runners do
not reference it. This moves the known 10.478-second first-live graph/JIT tax
into startup-to-ready time; it is not a cold benchmark improvement. See
[`2026-08-03-production-readiness-canary-offline.md`](notes/2026-08-03-production-readiness-canary-offline.md).

The secondary 32K attention lane is also prepared offline. The previously
208/208 exact but short-context-slower paired-row mechanism now has a
`long-full` component profile at exact contexts 8,192, 16,384, 24,576, and
32,640, projected only across the 12 full-attention layers. It requires at
least `0.25 ms/token` component saving before integration; no device run is
authorized or measured. The accepted-position/mixed-depth diagnostic remains
higher priority. See
[`2026-08-03-long-full-attention-screen-offline.md`](notes/2026-08-03-long-full-attention-screen-offline.md).

The primary 32K accepted-position decision is now automated offline. The new
analyzer requires the exact 1K warmup plus three 32,640-token rows and three
256-token sentinels, full oracle/cache/intrinsic consistency, zero long-row
acceptance beyond position 6, and positive beyond-position-6 acceptance in
every sentinel. Six CPU-only tests pass. There is still no successful input
artifact, so mixed-depth source work remains unauthorized. See
[`2026-08-03-mixed-depth-analyzer-offline.md`](notes/2026-08-03-mixed-depth-analyzer-offline.md).

### 2026-08-02 operational checkpoint

The latest q12 mixed-depth diagnostic stalled in distributed initialization
before model loading, after which the kernel reported repeated GuC timeouts and
resets on `0000:47:00.0`. Cleanup passed and the hypothesis remains unmeasured.
Steve authorized one clean reboot; the reboot and the bounded post-reboot gate
are now complete. All four sequential device probes and the single corrected
TP4 collective passed without retry, the collective had `4/4` clean teardowns,
and the bounded journal scan stayed clear. Evidence is sealed at
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/device-recovery-scheduler-gate-20260802T231513Z`.

The matched configuration-only scheduler alignment is complete: control
8,192/auto=8,182 passed 12/12 repeat-oracle exact, while candidate
8,202/explicit=8,192 changed token IDs and text on all eight selected long
rows at or above 8K. The candidate passed its intrinsic checks and all
diagnostic speed thresholds, but exactness is mandatory; the treatment is
rejected, was not retried, and produced no submission. See
[`2026-08-02-long-scheduler-budget-alignment-preregistration.md`](notes/2026-08-02-long-scheduler-budget-alignment-preregistration.md)
and
[`2026-08-02-scheduler-alignment-result.md`](notes/2026-08-02-scheduler-alignment-result.md).
Both services stopped cleanly, device scans remained clear, and the temporary
swap file was removed.

A subsequent source treatment remains ready offline, but its required A/B
failed, so it must not enter a component or endpoint gate under the current
preregistration. It fuses exact wide-prefill Q/K RMSNorm plus NeoX RoPE under a
default-off selector:

- vLLM `1234ff004d57f1f0c102bd2afff9690c16bf995a`;
- XPU kernels `a67a396245696a9df2a8929b445c721fa8899c92`;
- worktrees
  `/home/steve/src/laguna-vllm-wide-prefill-qknorm-rope-20260802` and
  `/home/steve/src/laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802`.

The oneAPI 2025.3 build, dispatcher registration, kernel static tests, 51
focused vLLM tests, Ruff checks, and independent source audit pass. Raw-BF16
XPU equivalence and performance remain explicitly unverified. Its required
scheduler dependency failed, so do not run the four-row/four-rank component
gate, aggregator, or endpoint described in
[`2026-08-02-wide-prefill-qknorm-rope-preregistration.md`](notes/2026-08-02-wide-prefill-qknorm-rope-preregistration.md).

Steve explicitly asked to continue optimizing. One fresh non-scored exact-small
portfolio 2x400 post-recovery smoke was preregistered in
[`2026-08-02-exact-small-postrecovery-preregistration.md`](notes/2026-08-02-exact-small-postrecovery-preregistration.md).
Its corrected runner wires both grouped-GEMM selectors through `env -i` and
was designed to prove their presence in all four workers, record the exact
grouped DSO maps, and require four-rank M12 row evidence. This launch did not
reach those post-health checks. The clean harness and lock-only commits were
frozen, but the one launch crossed the host-memory guard during KV-cache
initialization at `16,013,720 kB` MemAvailable and `341,476 kB` SwapFree. It
stopped before API health, graph capture, or any request. Cleanup and terminal
audit passed and both roots are sealed. Treat the authorization as consumed,
the candidate as still unmeasured, and the endpoint as locked. Result:
[`2026-08-02-exact-small-postrecovery-result.md`](notes/2026-08-02-exact-small-postrecovery-result.md).

The separately tagged resource-remediation successor is complete and consumed;
see [`2026-08-02-exact-small-swap24-result.md`](notes/2026-08-02-exact-small-swap24-result.md).
The exact 24 GiB swap layout cleared model/KV/graph/API initialization, but the
runner stopped before requests on an invalid proof assumption: vLLM worker
`setproctitle` can overwrite the kernel-visible initial environment block, so
post-title `/proc/<worker>/environ` is incomplete and cannot prove selector
propagation by absence. The resource journal independently failed on three
corrected RxErr events from the root-filesystem NVMe PCIe endpoint. All
owned processes stopped, ordinary swap was restored, the temporary file was
removed, and all roots were sealed. No candidate result exists. Only offline
worker-emitted selector-proof work is open; no new model/device/recovery action
is authorized.

The offline worker-proof repair is now complete and committed. The clean vLLM
worktree `/home/steve/src/laguna-vllm-worker-selector-evidence-20260803` is at
`d6a509e6f5bddd4c426ff970da4243c3af3e5306`; the strict host validator is main
repo commit `453c8d13d`, and the successor measurement leg/runtime packet is
main repo commit `4a0d961ef`. Offline suites pass `21/21`, `17/17`, and `10/10`.
The successor rejects inherited runtime and Python overrides, then requires
four worker-emitted selector records and four descriptor/inode-bound DSO
records after health and before metrics or inference. The consumed runner is
still byte-identical. Details:
[`2026-08-02-exact-small-worker-selector-proof-offline.md`](notes/2026-08-02-exact-small-worker-selector-proof-offline.md)
and
[`2026-08-02-exact-small-worker-proof-successor-preregistration.md`](notes/2026-08-02-exact-small-worker-proof-successor-preregistration.md).
There is deliberately no caller, component tag, fresh artifact root, or
execution lock. Do not create those or execute the successor without separate
authorization. The NVMe journal failure continues to prohibit retries and all
model, device, probe, reset, or recovery work; continue offline only.

The remaining material below is historical lane context, not authorization to
run another component, model, or endpoint gate.

Current promoted result and exact artifacts:
[`2026-07-31-shared-elementwise-m12-record.md`](notes/2026-07-31-shared-elementwise-m12-record.md).
Before this closeout, the research direction was to continue reducing real
device submissions inside captured graph segments or the dominant MoE
mainloop. The remaining conventional gap to 130 is `4.5380268362249 tok/s`
(`3.6170536154%` relative to the current row). This is strategic context only.

The latest bounded grouped-MoE scheduling screen is closed. Full packed
N-major ordering and the complete preregistered C=4/8/16 hybrid chunk sweep
were all raw-BF16 exact, but every ordering was slower than the protected
same-expert scheduler. C=16 was the least harmful at `0.991484x`; it still
missed both the per-shape and summed promotion gates. No production metadata,
four-rank smoke, endpoint run, or recovery action followed. Do not retry this
interleave family or count it as headroom. See
[`2026-08-01-m12-hybrid-nchunk-preregistration.md`](notes/2026-08-01-m12-hybrid-nchunk-preregistration.md).

The exact small-component portfolio previously passed its preregistered one-B70
component gate and was the active bounded treatment at that time. It combines
the exact M12 mapped gather/scale/add tail with the jointly compiled no-K-loop-
barrier and scale-lane-dedup grouped kernel. All 12 raw-BF16 comparisons
passed, inputs were immutable, and the direct joint saving was
`0.3082524 ms/cycle` against a
frozen `0.30 ms/cycle` threshold. Candidate-only vLLM/XPU integration and its
runtime lock are committed. The first non-scored TP4 smoke stopped before
model loading at the oneCCL PCIe-topology initialization boundary and timed
out; no request or candidate dispatch occurred. Teardown and post-failure idle
checks passed, and no reset/reboot/retry occurred. Collective health was later
restored. The post-recovery smoke above then stopped at its resource guard
before any request, so the portfolio still has no model or endpoint evidence.
Its historical component record is
[`2026-08-01-exact-small-component-portfolio-preregistration.md`](notes/2026-08-01-exact-small-component-portfolio-preregistration.md)
and the protected record trees must remain preserved.

Do not implement the proposed paired-K32 split-barrier variant. A follow-up
dominance audit found it is subsumed by the exact full-removal result: retaining
half the barriers cannot plausibly beat removing all of them, and full removal
improved the summed component by only `0.3906%`. The pairing idea would need an
unsupported non-monotonic phase-alignment effect to matter; no evidence points
there. Mainloop work must attack a different cost class rather than another
barrier spelling.

The target inline-gather correctness failure is now both localized and repaired
at the bounded model gate. The installed oneCCL runtime corrupted the captured
Laguna gather transaction under changing inputs, while pinned public libccl
`4ceafd15c` passed 512/512 transaction replays on all ranks. Under that public
runtime, a matched prefix-24 model arm passed 2x400 exact with zero cache hits,
changed target topology from `146/145` to `122/121`, and matched all 402 traced
tensors on all four ranks—including the layer-0 gathered O-projection that
previously diverged. The required fresh 13x512 lifetime gate then failed on
request 0: target capture completed on ranks 0-2 but not rank 3, no target rank
replayed, and `execute_model` timed out at one emitted token. Cleanup and idle
checks passed without recovery. Direct captured target gathers under public
libccl `4ceafd15c` are closed: do not retry, widen to 96, score, or promote.
See
[`2026-08-01-public-oneccl-prefix24-service-lifetime-result.md`](notes/2026-08-01-public-oneccl-prefix24-service-lifetime-result.md).

Read the
[accounting correction](notes/2026-07-26-throughput-window-accounting-correction.md)
before making any speed claim. The approved receipt remains historical
evidence and must not be duplicate-submitted.

Do not resume from the former 94.920 record, the obsolete recovery block, or
the abandoned tree/selector ideas. They are historical evidence, not current
work.

## Record identity

| Field | Value |
| --- | --- |
| Target | `poolside/Laguna-S-2.1-INT4` at `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb` |
| Draft | `poolside/Laguna-S-2.1-DFlash-INT4` at `5e07c246915c86dc6920fead03d019989224f2ba` |
| vLLM | `1a7f61feffbc61b21b73f812d231c7426386ccdc` |
| XPU kernels | `99886d783372e621941228250091dc8ebdc1595d` |
| Layout | TP4+EP4, one active generation |
| Target verifier | exact width 12 |
| DFlash | depth 11, greedy draft, standard rejection |
| Graph | audited Breakable PIECEWISE capture size 12, 146 graphs / 145 eager breaks per rank |
| KV | BF16 |
| Treatment | segmented inline DFlash attention, decode-only GRF128, contiguous `[expert,K/32,N]` BF16 target scale clones, exact M12 Q/K RMSNorm plus RoPE, and exact M12 shared elementwise fusions |
| Selectors | `VLLM_XPU_LAGUNA_DECODE_GRF128=1`, `VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=1`, `VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1`, `VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=1` |

The intended separate FP8 draft-LM-head path exists in source, but its expected
runtime preparation message is absent from the record log. Do not attribute
the measured gain to that head. The evidence-backed treatment is limited to
the 31 logged draft projections and auxiliary workspace.

## Formal command and artifact

```bash
experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh \
  candidate B1 RUN_DIR 12 11 1 0 0 1 0 0 0 1 1 0 0 '' 64 0 '' \
  6 0 1 0 0 1 0 0.90 0 0 0 1 0 1 1 0 0 0 1
```

Sealed run:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-shared-elementwise-m12-formal-20260801T053000Z
```

Promoted records:

- exact source bundles and combined patches:
  `patches/laguna-s-2.1-xpu-b70/`;
- packet:
  `data/laguna-shared-elementwise-m12-record-20260731.json`;
- note:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-shared-elementwise-m12-record.md`;
- metric correction:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md`;
- standalone reproduction:
  `repro/laguna-s-2.1-int4-b70-125tps-20260731/`;
- reproducibility provenance audit:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-reproducibility-provenance-audit.md`;
- submission queue:
  `data/localmaxxing-laguna-s-2.1-int4-b70-shared-elementwise-m12-125.462tok-20260731.queue.json`;
- submission response:
  `data/localmaxxing-responses/laguna-s-2.1-int4-b70-shared-elementwise-m12-125.462tok-20260731.response.json`.

Durable learning indexes:

- complete current endpoint-win ladder, research victories, transfer
  conditions, and future-model recording template:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-08-01-optimization-victories-and-transferable-methods.md`;
- Laguna-specific wins, negative results, graph/correctness lessons, and
  harness rules:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-campaign-transfer-ledger.md`;
- official FP8-KV recommendation versus the record's deliberate BF16-KV
  contract:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-kv-cache-precision-decision.md`;
- reusable cross-model rules:
  `docs/research-workflow-playbook.md`.

The official quantized checkpoint declares calibrated per-tensor FP8 KV and
vLLM `auto` resolves to it. This record explicitly overrides that with BF16
because the declared teacher is BF16, the benchmark used at most 0.5% of its
allocated KV capacity, and the earlier controlled Laguna screen found FP8
exactly doubled capacity but was `4.132%` slower and changed outputs. Do not
confuse the record's FP8 DFlash projection weights with its BF16 KV cache.

## Gates that passed

- fixed realistic suite, 13 unique prompts;
- each prompt invoked exactly once;
- no warmup generation and no retry;
- first valid score is the reported score;
- 13/13 token IDs and text bitwise exact vs the canonical q1 teacher;
- `cached_tokens=0` on all 13 requests;
- full-512-output-then-next 2/2 and rollover 1/1 exact; the 863-token prompt
  is the final row, so no long-context-then-next claim is made;
- target capture and replay witnessed on all four ranks;
- 146/145 topology exact on every rank;
- 73-second prestart and poststop idle intervals;
- clean service, worker, and port teardown;
- target model, target LM head, verifier, sampling policy, and target KV
  semantics unchanged.

## What went wrong earlier

The old recovery wrapper resolved a nonexistent scratch-local probe path.
Several summaries therefore reported `0/4` even though the probe never entered
Python. Driver reload, FLR, and shared-memory cleanup conclusions made from
those summaries were unfounded. Later corrected full-model runs proved the live
TP4/XCCL path healthy, so the old recovery block is closed.

The submission helper also pointed speed records at the retired
`/api/benchmarks` route and accepted an HTTP 200 HTML shell as success. It now
uses `/api/speed-tests`, validates the exact projected request through the
authenticated server dry-run, and accepts only HTTP 201 JSON containing a
nonempty ID and status.

## Rules for any future optimization

1. Preregister the selector, treatment, control, primary metric, and stop
   conditions before running a score-bearing leg.
2. Preserve the fixed suite and canonical teacher. Never change the target,
   omit slow prompts, cherry-pick starts, move setup outside the scored window,
   warm the service, or substitute a more favorable metric.
3. Require one active generation, `cached_tokens=0`, one invocation per prompt,
   no prefix/history/response reuse, and target verification of every accepted
   draft token.
4. Diff the complete run identity before interpreting speed. Require exact
   source commits, model revisions, binaries, flags, graph capture sizes, and
   146/145 topology.
5. Inspect the source file after editing it. Inspect per-rank logs and explicit
   execution markers before trusting summary counters.
6. Treat a failed or missing probe as unknown. Never escalate privileged
   recovery unless the probe proves that it executed and classifies the
   failure boundary.
7. Keep every negative patch/result in the experiment ledger, commit focused
   changes, and leave all experimental selectors default-off.
8. Report the first valid result honestly, whether it wins or loses.
9. For timestamp windows, record event and interval counts separately. `N`
   timestamped events span `N-1` intervals; report the conventional interval
   field for new goals and qualify the historical compatibility field.

No recovery or hardware action is pending. Closing the conventional
`0.05827875982973 tok/s` gap, or any other benchmark work, requires a new
preregistered experiment.
