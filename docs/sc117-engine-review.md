# SC117 engine review and reusable four-card direction

October 25, 2026. The current two-B70 engine is substantially faster, with
unchanged outputs on the retained twelve-prompt comparison. It remains a
research engine: independent-reference fidelity and a complete portable
release are unfinished. Four-card single-conversation performance is unmeasured.

## What the evidence establishes

| Question | Finding | Evidence and limit |
| --- | --- | --- |
| Did decode improve? | Ordinary all-prompt median **27.9186 → 47.8873 tok/s**, 1.715× | Twelve retained service observations; full-response rate, not the certified class-balanced first-99-interval metric. All twelve prompt/output token arrays and stored text hashes match. |
| Why did reports say 28.00 → 47.95? | The old harness selected the upper middle of twelve rates | The offline audit computes the average of the two middle values. Historical receipts remain unchanged. |
| Is the engine identical to the CPU reference? | **5,959/5,965 teacher-forced positions agree; six differ** | The reference reads the engine's output prefix. This is neither full free-running parity nor bit-faithfulness. The discrepancy remains unexplained. |
| Does grouping prompt attention help? | Rank-1 harness: 31,612.5 → 30,758.3 ms for 3,000 rows | About 2.7% less time (about 2.8% greater row rate), warm JIT, synthetic streams, four subsequent decode steps. The note reports 1,079 matching buffers; its linked summaries do not contain the comparison receipt. Full service qualification of pf96 is pending. |
| Did tensor splitting help? | The tested two-device rank-1 split broke even | The quoted 16.72 ms excludes the first two samples; all-sixteen median is 16.79 ms. This is a stage diagnostic, not a complete two- versus four-card service comparison. |
| Is prompt reading fast enough? | A retained 3,000-token service check took about 31 seconds | A separate observation; the matching standard 512-token prefill benchmark is not established here. No derived context curve is claimed. |

The [repeatable offline audit](../experiments/own-xpu-runtime/research/review-2026-10-25/audit_service_evidence.py)
and its [hash-bound report](../experiments/own-xpu-runtime/research/review-2026-10-25/service-evidence-audit.json)
separate stored statistics from recomputed ones. Run from the repository root:

```bash
python3 experiments/own-xpu-runtime/research/review-2026-10-25/audit_service_evidence.py
```

The old service summaries do not retain the observed `cached_tokens` value,
and their harness treated a missing value as zero. They cannot independently
certify cold requests. Resident model weights and compiled kernels are valid;
prompt, KV or response reuse must be absent and explicitly recorded for a
benchmark claim.

The [F32 reference result](../experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/e-reference/RESULT-F32.md),
[grouped-attention screen](../experiments/own-xpu-runtime/research/prefill/2026-10-25-grouped-attention.md),
[TP closeout](../experiments/own-xpu-runtime/research/tp/2026-10-25-exact-tp-closeout.md)
and [negative-result ledger](../experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md)
retain the full scope. In particular, HC combine+norm was an unsuccessful
candidate with divergent rank-1 state; “every attempted change was exact” is
incorrect. Accepted optimizations and rejected experiments must remain distinct.

## The engine we are building

The owner's direction is one reusable engine with model-family adapters,
quantization support and measured tuning profiles. Intel B70 and Qwen-like
architectures are the immediate focus. One, two, four and six cards are target
configurations; current executable support is narrower. DeepSeek 4 Flash is a
possible future family, not an already supported Qwen variant.

Keep four concerns separate:

1. **Model description:** layer types and dimensions, attention/recurrence,
   experts, tokenizer and draft compatibility, and pinned tensor identities.
2. **Quantization kernels:** decode the actual storage type of each tensor;
   never infer every tensor's format from a label such as IQ3_S. Preserve
   existing tuned kernels and arithmetic variants.
3. **Placement and execution:** topology, whole-layer ranges, device mapping,
   communication, memory lifetimes and speculative commit/rollback. Reject
   unsupported combinations before allocating or launching.
4. **Tuning and evidence:** measured choices keyed by model revision, quant,
   arithmetic, topology, workload and kernel identity. No universal default
   inferred from a single model or a diagnostic microbenchmark.

The [canonical source tree](../experiments/own-xpu-runtime/engine/README.md)
already has shared typed BF16/F32 buffers and kernel dispatch. Preserve that
foundation. The present model geometry, two-rank protocol and several format
site tables still contain SC117/Flash-Next assumptions; a generic front end
must not claim those restrictions have disappeared.

The new [CPU placement planner](../experiments/own-xpu-runtime/engine/planning/README.md)
reads existing tensor metadata and emits hash-bound 1/2/4/6-stage candidates.
It separates the host lookup table and global weights from packed layer
weights. Optional measured per-layer costs can replace weight balancing.
Its output is a planning artifact, not runtime admission or a speed prediction.

## Four-card speed work

Prioritize **one conversation's latency**, and measure multi-user throughput
separately. Two independent two-card replicas do not double one user's speed.
The current tensor-split implementation is not a promising default: its
gathers consumed the saved work. Retain it for different shapes, larger
matrices and improved communication; this result is not a general ceiling.

The next useful experiment is recursive draft acceptance two and three tokens
ahead on the current F32 target. Count actual dependent proposals joined to
the verified prefix; consecutive one-step hits are not that measurement.
Reuse the [existing depth-two probe](../experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe/README.md)
and [causal rollback design](../experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/DESIGN.md).
The older depth-two implementation lost about 47% under its old scheduling;
simply increasing depth is not a speed optimization. A four-stage design
must overlap useful work and account for draft cost, missed proposals,
pipeline bubbles, transfer time, EOS and cancellation.

Before an end-to-end PP4 result, require:

- general stage boundaries with exact layer/tensor coverage;
- target-only equivalence to the two-card F32 engine;
- full-state equality for accepted and rejected speculative prefixes,
  including forced rejection at each position, EOS and reset;
- identical batched and per-row prompt state;
- complete per-device and host-memory admission, with the **29,137,853,440-byte
  host lookup copy** included alongside any multi-device allocation shadow;
- the full cold suite with retained cache counts, timestamp windows, per-class
  statistics and independent-reference limits visible.

The owner authorized use of all four cards and incident-reviewed GPU resumption
in this session. Stop the vision service gracefully when the quad test is ready.
No reboot, driver reset, power/memory-setting change or retry loop is authorized.
New faults halt new requests and preserve evidence. Live state belongs in
[CURRENT.md](../CURRENT.md), not in this research guide.

## Publishing the complete engine and recipe

GitHub and the public sites can publish the source, current observations,
failed experiments and these limitations now. They must not present SC117 F32
as the older Unsloth UD-IQ3_XXS/BF16 result. Preserve both model identities and
their independent records.

The current source build uses Intel oneAPI compiler 2026.0 at
`/opt/intel/oneapi/compiler/2026.0/bin/icpx`. From a checkout, this command
compiles but does not execute the engine:

```bash
python3 experiments/own-xpu-runtime/engine/build.py /absolute/build-directory --jobs 4
```

Check capacity and toolchain first. The build receipt hashes the actual compiled
dependencies. `build-manifest.json` is the historical consolidation record and
compile recipe; its original file hashes are not current source pins.

The [service instructions](../experiments/own-xpu-runtime/gsq-rco-iq3s/serving/lan/README.md)
describe the lab deployment, not a copy-anywhere installer. Its absolute paths,
device mapping, model/draft manifests and lab admission dependencies still need
a portable configuration layer. A complete release additionally needs a clean
source build, licensed/pinned dependencies, runtime and fidelity gates, binary
and build-log assets, and download-and-rehash verification under the
[publication standard](recipe-publication-standard.md). Research source
availability is not a completed or quality-qualified release. No new
LocalMaxxing record is submitted from these service observations.
