# SC117 engine review and reusable four-card direction

October 25, 2026. The current two-B70 engine is substantially faster, with
unchanged outputs on the retained twelve-prompt comparison. It remains a
research engine: independent-reference fidelity and a complete portable
release are unfinished. Four-card target-only execution now passes a bounded state comparison;
a faster four-card speculative service remains unfinished.

## What the evidence establishes

| Question | Finding | Evidence and limit |
| --- | --- | --- |
| Did decode improve? | Ordinary all-prompt median **27.9186 → 47.8873 tok/s**, 1.715× | Twelve retained service observations; full-response rate, not the certified class-balanced first-99-interval metric. All twelve prompt/output token arrays and stored text hashes match. |
| Why did reports say 28.00 → 47.95? | The old harness selected the upper middle of twelve rates | The offline audit computes the average of the two middle values. Historical receipts remain unchanged. |
| Is the engine identical to the CPU reference? | **5,959/5,965 teacher-forced positions agree; six differ** | The reference reads the engine's output prefix. This is neither full free-running parity nor bit-faithfulness. The discrepancy remains unexplained. |
| Does grouping prompt attention help? | Rank-1 harness: 31,612.5 → 30,758.3 ms for 3,000 rows | About 2.7% less time (about 2.8% greater row rate), warm JIT, synthetic streams, four subsequent decode steps. The note reports 1,079 matching buffers; its linked summaries do not contain the comparison receipt. The later c13 engine passed full target-state and batched-prefill startup gates; this does not recreate the missing original synthetic comparison receipt. |
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

The recursive depth probe is now complete on twelve prompts and 5,965 output
positions. Every output matches the earlier GPU engine, and all 5,965 probe
restoration checks passed. Two-token complete-prefix success is 3,313/5,953
(**55.65%**); three-token success is 2,390/5,941 (**40.23%**). Conditional
second/third-token accuracy is 73.09%/72.25%. Ending positions without enough
verified future tokens are censored. These are actual dependent proposals,
not consecutive one-step hits; instrumented timing is not a speed result.
See the [probe result and retained traces](../experiments/own-xpu-runtime/research/review-2026-10-25/depth-probe-result.md).
Reuse the [existing depth-two probe](../experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe/README.md)
and [causal rollback design](../experiments/own-xpu-runtime/stage2/packet71c-depth2-engine/DESIGN.md).
The older depth-two implementation lost about 47% under its old scheduling;
simply increasing depth is not a speed optimization. A four-stage design
must overlap useful work and account for draft cost, missed proposals,
pipeline bubbles, transfer time, EOS and cancellation.

The first [native two/four-stage proof](../experiments/own-xpu-runtime/research/review-2026-10-25/pp-proof/RESULT.md)
passes: 32 output IDs and 2,065 canonical state buffers agree after the same
87-token prompt. The four-stage boundaries are 0/13/25/37/48. Sequential target
steps averaged 39.707 ms on four cards versus 31.894 ms on two (24.50% slower).
This is a correctness foundation; the existing two-card speculative service
remains the faster established path. The [next scheduling design](../experiments/own-xpu-runtime/engine/planning/wavefront-next.md)
separates tentative completion from verified commit and restores rejected suffixes.

The subsequent [overlap and forced-miss proof](../experiments/own-xpu-runtime/research/continuation-2026-10-25/wavefront-proof-a/RESULT.md)
also passes: all 32 outputs and 2,065 canonical buffers match after six deliberately
wrong proposals, including consecutive misses. The affected stages performed 13
complete byte-verified restorations and all four processes exited cleanly. This
uses scripted proposals to test correctness; it establishes no speed gain. Live
integration uses the existing draft weights. The owner has excluded draft training.

Before a four-card speculative service result, require:

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
in this session. The vision service was stopped gracefully after the probe to free 27/43.
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

A committed 224-file research-source archive from `d882b4df4` also rebuilt in a
separate extracted directory with oneAPI 2026.0. The [build evidence](../experiments/own-xpu-runtime/research/review-2026-10-25/source-d882-rebuild.json)
records archive and binary hashes. This is a clean extracted-source build on the
same host, not a clean-host runtime or portable service qualification.

The [portable deployment preparation](../experiments/own-xpu-runtime/engine/deployment/README.md)
now separates immutable model/quant identities from local paths and file metadata.
It verifies complete model hashes, generates a separate authenticated build header,
and produces explicit two/four-card command plans. The installed target, existing
draft and tokenizer passed one complete authentication pass. CPU validation covers
25 preparation/launch checks and 13 source-bundle checks. A clean generated-header
build, guarded portable controller, runtime parity and clean-host installation
remain qualification work. The existing draft loader requires 30.05 GB of source
shards even though its selected tensors total 2.70 GB.

After the quad proof, the normal two-card service was restored on engine
`51ebe7496793`. Its F32-state, batched-prefill and continuation gates passed.
The [new cold twelve-prompt service check](../experiments/own-xpu-runtime/research/review-2026-10-25/normal-service-result.json)
measured **47.9706 tok/s** ordinary median, with explicit `cached_tokens=0` on
every request and all 5,965 output IDs plus twelve text hashes unchanged. This
confirms the earlier roughly 48 tok/s observation; it is not a new certified record.

The [downloadable 228-file source snapshot](../downloads/own-engine/ownrt-source-1cab4a1e5.tar.gz)
from `1cab4a1e5` also passed a fresh extracted-source build; its
[receipt](../experiments/own-xpu-runtime/research/review-2026-10-25/source-1cab-rebuild.json)
binds the public archive checksum and resulting binary. It preserves the same
research-source-only boundary: this was not a clean-host runtime qualification.
