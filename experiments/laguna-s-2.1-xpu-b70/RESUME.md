# Laguna S 2.1 resume point

Last updated: 2026-08-01 America/Toronto

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

Current result and exact artifacts:
[`2026-07-31-shared-elementwise-m12-record.md`](notes/2026-07-31-shared-elementwise-m12-record.md).
The next bounded exact work should continue reducing real device submissions
inside captured graph segments or the dominant MoE mainloop. The remaining
conventional gap to 130 is `4.5380268362249 tok/s` (`3.6170536154%` relative
to the current row).

The latest bounded grouped-MoE scheduling screen is closed. Full packed
N-major ordering and the complete preregistered C=4/8/16 hybrid chunk sweep
were all raw-BF16 exact, but every ordering was slower than the protected
same-expert scheduler. C=16 was the least harmful at `0.991484x`; it still
missed both the per-shape and summed promotion gates. No production metadata,
four-rank smoke, endpoint run, or recovery action followed. Do not retry this
interleave family or count it as headroom. See
[`2026-08-01-m12-hybrid-nchunk-preregistration.md`](notes/2026-08-01-m12-hybrid-nchunk-preregistration.md).

Do not implement the proposed paired-K32 split-barrier variant. A follow-up
dominance audit found it is subsumed by the exact full-removal result: retaining
half the barriers cannot plausibly beat removing all of them, and full removal
improved the summed component by only `0.3906%`. The pairing idea would need an
unsupported non-monotonic phase-alignment effect to matter; no evidence points
there. Mainloop work must attack a different cost class rather than another
barrier spelling.

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
