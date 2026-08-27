# neural.download packet standard (v1, 2026-08-22)

Purpose: every model on the neural.download page ships as a **packet** —
benchmarks, any required patches, and a reproducible recipe — so users get
wide variety with honest, measured expectations. Packets inherit the lab's
evidence standards; nothing on the page is a guess.

Agents creating or updating these surfaces must use the repository-local
`$publish-model-package` skill. Outside submissions first use
`$review-model-contribution`; adopted work then follows the same package rules.

## Packet contents (one directory per entry, `repro/<package-id>/`)

1. **Identity** (`README.md` header + `manifest.sha256`)
   - Model family, size, quant(s); exact GGUF file name(s), byte size,
     SHA-256, source repo, pinned revision.
   - Packet base: pinned upstream `llama.cpp` commit, exact cmake configure
     line, toolchain (oneAPI version), target device (Intel Arc Pro B70,
     bmg-g31 AOT).
   - Companion files where applicable (vision mmproj, MTP/draft heads),
     each pinned and hashed.

2. **Recipe**
   - Exact server command(s): context size, KV cache type, flash
     attention, batch/ubatch, device selection. Copy-paste runnable.
   - Measured VRAM footprint at each published operating point.
   - Up to three operating points per model: **max-context**, **balanced**,
     **speed** — each with its own measured numbers. Never publish an
     operating point that was not actually loaded and measured on a B70.

3. **Benchmarks** (data JSON + summary table in README)
   - Decode: median within each input class, then median across those class
     medians, using conventional 99-interval tok/s on the 12-prompt realistic
     suite, each prompt once,
     512-token natural-completion cap, `cached_tokens=0` verified per request;
     two fresh-server runs, both numbers published (band, not cherry-pick).
     Model residency and completed kernel compilation are allowed; prompt/KV/
     response caches, learned/repeated-prompt drafting, selected fixtures, and
     prompt subsets are not. A natural EOS after the 100-event metric window is
     valid and its actual token count must be reported. Keep the ordinary
     all-prompt median as a secondary diagnostic only.
   - The suite must identify and contain multiple prompt classes, including at
     least prose, code, analysis, operations, and documentation/structured
     writing. Twelve variants of one easy shape are not a varied suite.
   - TTFT and prefill rate at a standard 512-token prompt.
   - For MoE models, note active-parameter count next to the rate so users
     understand why a 30B-A3B outruns a dense 27B.

4. **Quality and expectations**
   - Repeat determinism (8x same-prompt hash stability), arithmetic, copy,
     JSON-schema canaries; long-context needle at a depth appropriate to
     the published max-context point.
   - New families get **self-consistency + sanity canaries**, not oracle
     equality claims (there is no cross-model oracle). The README states
     explicitly what was and was not tested.
   - Every optimized path must also match its registered unoptimized or
     unchanged-target oracle under the lane's declared tolerance. A new-family
     sanity battery can qualify a stock candidate, but it cannot prove that a
     later optimization preserved outputs.
   - Known limitations verbatim (e.g. context ceilings by KV budget,
     quality class of the quant).

5. **Patches**
   - Default is stock pinned upstream. Any patch needed for bring-up or a
     material speed win lives in `patches/` with SHA-256s, applies cleanly
     to the pinned commit, and is a candidate for upstreaming. Packets say
     whether their numbers are stock or patched.

6. **Discovery and credit** (`packages/<id>/package.json`)
   - Normalize model family, variant, quantization, card count, runtime, OS,
     native/container delivery, modalities, use cases, and one evidence-linked
     featured metric so a generated library can filter dozens of deployments.
   - Record every integrated contributor by the exact delta, recognition
     status, validated effect (or explicitly unmeasured effect), and in-repo
     evidence. A runtime or model dependency is not contributor credit by
     itself, and a repackaged collection is never made the source of a
     lab-developed recipe.
   - Regenerate `packages/catalog.json` from the manifests; the public library
     consumes that derived file, never a second hand-maintained list.

7. **Context performance profile** (optional until measured)
   - Record decode after TTFT, prompt-processing/prefill rate, and TTFT at
     several actual prompt/context lengths, ideally from short context through
     the package's supported maximum.
   - Keep concurrency, output length, cache state, sampler, quantization,
     runtime flags, and service profile fixed across the curve. If an operating
     profile differs from the headline lane, label that difference directly.
   - Store measured points and aggregation in repository evidence, then expose
     them through `performance_profiles`; never interpolate a one-point
   headline or mix unrelated experiments into a line.

8. **Aggregate concurrency profile** (optional until measured)
   - Use an explicit `x_metric: concurrent_sequences` profile and record raw
     aggregate decode as `value`; `per_user_value` may accompany it.
   - State whether the harness is raw-engine batching or an HTTP service test.
     Never relabel engine sequences as users/sec, and never fill missing
     concurrency points from a projection.
   - Hold prompt/output shape, cache state, batching mode, runtime flags, and
     hardware fixed. Preserve ascending/descending or matched-repeat evidence
     when warmup and run order materially affect the curve.

## Integrity rules (inherited from the lab standard)

- Every input pinned by SHA-256; model files sealed 0444 after verification
  with a `DOWNLOAD-MANIFEST.txt` in the model directory.
- Rates are conventional-median only; no legacy-inclusive accounting on the
  page. Failed runs are not silently rerun; bands reflect what happened.
- A package may retain a runnable recipe with `featured_metric: null` while a
  strict headline is pending. It must state `library.benchmark_status`; public
  pages render “strict headline pending” instead of forcing a diagnostic number
  into the slot.
- Promotion requires two separate decisions: the performance workload gate and
  the lane's exact-output/quality plus repeat-determinism gate. Neither implies
  the other. High-acceptance fixtures and short output-cap screens remain
  diagnostic even when their output checks pass.
- Raw performance and quality evidence must live in this repository (or in a
  deliberately tracked, hash-addressed evidence bundle), not only as filenames
  on an unshared host. External-submission builders require a
  `neural.download.promotion-attestation.v1` file that hash-binds the exact
  speed artifact to the model/runtime/optimization identity and independent
  quality, target-oracle, repeat, fresh-server, and no-quality-loss decisions.
  See the [promotion attestation format](promotion-attestation.md).
- No packet publishes speculation-assisted rates as the headline unless the
  packet IS a speculation package (then both target-only and assisted rates
  appear, labeled).

## Pipeline position (one pipeline, two layers)

Packets are the **publication layer** on top of the lab's
[model-intake pipeline](../model-intake/README.md) and its
[first-wave bring-up protocol](../model-intake/bringup-protocol.md)
(intake states: queued -> downloaded -> bring-up -> baseline -> optimized
-> packaged). A packet is produced only from a model that has passed
intake verification (direct + ordinary I/O hashes at the catalog
destination) and the preregistered bring-up/baseline runner
(`scripts/run-model-intake-baseline.sh` +
`scripts/bench-model-intake-baseline.sh`, 1 B70, f16 KV, 8K, target-only
diagnostic). Bring-up order follows the protocol's preregistered table
(Ornith 9B first), not this document's lane table. The packet then adds
the fuller published benchmarks (512-token windows, operating points,
canaries) per this standard. The Qwen3.8-27B flagship package is a
manager-directed addition outside the intake catalog; it follows the same
verification and packet rules.

## First wave (2026-08-22) and the question each packet answers

| Slug | Model | Lane | Question |
|---|---|---|---|
| `lfm2.5-2.6b` | LFM2.5 2.6B Q8_0 | novice | smallest honest single-command B70 recipe |
| `ornith-1.5-9b` | Ornith 1.5 9B Q8_0 | beginner-plus | recent one-card model; beginner package candidate |
| `nemotron-3.5-lightning-30b-a3b` | UD-Q4_K_M | mid MoE | does the family run on Intel without NVIDIA's NVFP4 runtime |
| `ornith-1.5-35b-a3b` | Q4_K_M | enthusiast MoE | validate the family + an outside one-B70 performance claim independently |
| `qwen3.8-27b-256k` | UD-Q4_K_XL vs UD-Q5_K_S fit-off + mmproj + MTP draft | flagship | highest quant that truly serves ~256K + vision + draft on one B70 |

Architecture notes established at intake: Ornith 1.5 = `qwen35moe`
(256 experts / 8 used, 41 layers, GQA 16/2, 262144 native) — supported by
today's upstream. Nemotron 3.5 Lightning and LFM2.5 arch strings to be read
from their GGUF headers at verification.
