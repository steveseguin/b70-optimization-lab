# Muse-Glimmer-30B Q8/WOQ on 4x B70: 100 tok/s reproduction

> **Certification: `candidate-portable-repro`, not a starter guide.** Install,
> restore, launch, and validation material is closed for the lab's own hosts;
> clean-host certification is still pending. The open items are listed under
> this guide's `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json).

This recipe preserves the 2026-08-13 no-training Muse result:

- target: Muse-Glimmer-30B `UD-Q8_K_XL`;
- drafter: the published Muse assistant converted to BF16 GGUF; no drafter
  training was performed;
- hardware: four Intel Arc Pro B70 32 GB cards, TP4, one active request;
- modality: text only; no mmproj/vision path was measured;
- runtime: llama.cpp/SYCL with fixed-width-16 direct-strided oneDNN WOQ and
  distributed ARGMAX/local-winner reuse;
- canonical full-256 arithmetic means: **100.088** and **100.649 tok/s**;
- cold 15-prompt conventional first-100 median: **161.900 tok/s**, p10
  **108.574**, all prompt-cache counters zero.

This is a Q8/WOQ, target-verified benchmark. It is not BF16, lossless,
universally token-exact, or 100 tok/s on every prompt/full natural response.

Prerequisites beyond the pinned Intel toolchain are Python 3, CMake, GNU Make,
Git, `curl`, `jq`, `rg`, `flock`, `sha256sum`, and (for model reconstruction)
the Hugging Face `hf` CLI plus the Python dependencies required by
`convert_hf_to_gguf.py`.

## 1. Verify the preserved evidence offline

```bash
cd /path/to/llm-optimizations
python3 repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/verify-evidence.py
(cd repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813 && sha256sum -c SHA256SUMS)
(cd patches/muse-glimmer-30b-b70 && sha256sum -c SHA256SUMS)
```

The evidence folder contains the two canonical result rows, the retained
second server log, the full 15-prompt token/timestamp capture, its final server
log, ARGMAX parity, TOP_K reference parity at 256/512, and the 1024-token code
gate. Run 1's canonical server log was overwritten by the historical harness;
that limitation is recorded rather than hidden.

## 2. Restore the exact source

```bash
repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/restore-source.sh \
  "$HOME/src/llama.cpp-muse-q8-woq-repro"
```

This clones public llama.cpp at
`030ebb558a5820b444a8f836ed5cdd46c9b4bd7a` and applies the complete
base-to-record patch. The private-history bundle and split final patches are in
[`patches/muse-glimmer-30b-b70`](../../patches/muse-glimmer-30b-b70/README.md).

## 3. Obtain the models

The target is directly hash-pinned:

```text
https://huggingface.co/unsloth/Muse-Glimmer-30B-GGUF/resolve/faa5b025c584459c13febfa5c59883516710ae39/Muse-Glimmer-30B-UD-Q8_K_XL.gguf
SHA-256 e63bf23b7710ecdea2579e4b1de58980c4a2b446e8ecf48b782cfcefd2e31770
bytes   32300651040
```

The BF16 assistant GGUF was converted locally from
[`meta-models/Muse-Glimmer-30B-assistant`](https://huggingface.co/meta-models/Muse-Glimmer-30B-assistant)
with tokenizer/config metadata from
[`meta-models/Muse-Glimmer-30B`](https://huggingface.co/meta-models/Muse-Glimmer-30B):

```bash
python3 convert_hf_to_gguf.py ASSISTANT_DIR \
  --outfile dflash-bf16.gguf --outtype bf16 \
  --target-model-dir TARGET_METADATA_DIR
```

The authoritative output is 5,125,206,048 bytes with SHA-256
`4a624b08e65047d94768f9ada606a1c42a1a7c08e05fc1ed0be876f1606b2ab2`.
The original download-time revisions and complete input hashes were not
retained. Current observed revisions are in [`manifests/models.json`](manifests/models.json),
and [`scripts/download-models.sh`](scripts/download-models.sh) reconstructs
from them but fails closed unless the final GGUF matches. If it does not match,
obtain the hash-pinned GGUF from the record operator or treat the conversion as
a new model identity and rerun all gates.

## 4. Build

The record host used Ubuntu 24.04.4, kernel 7.0.0-28, Intel GPU runtime
26.18.38308.1, Level Zero 1.15.38308+1, IntelLLVM/oneAPI 2026.0, and oneDNN
3.11.2. Full identity is in [`manifests/toolchain.json`](manifests/toolchain.json).

```bash
export LLAMA_CPP_ROOT="$HOME/src/llama.cpp-muse-q8-woq-repro"
JOBS=2 repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/build.sh
```

The record binary/library hashes are in [`manifests/source.json`](manifests/source.json).
Rebuilt hashes can differ across toolchains, so report both your source/model
identity and your rebuilt binary hashes.

## 5. Operational preflight

Stop every GPU-backed production service first, confirm all four cards are
idle, and use the canonical nonblocking lock. Do not run this beside another
benchmark or server. The runner refuses a busy lock and refuses to overwrite an
output directory.

```bash
export MUSE_TARGET_MODEL=/models/Muse-Glimmer-30B-UD-Q8_K_XL.gguf
export MUSE_DRAFT_MODEL=/models/dflash-bf16.gguf
export LLAMA_CPP_ROOT="$HOME/src/llama.cpp-muse-q8-woq-repro"
```

## 6. Replay the canonical full-256 gate

```bash
repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/run-canonical-256.sh \
  /new/results/muse-canonical-256
```

This starts two fresh servers, preserves each log separately, runs the three
fixed prompts at 256 generated tokens, and requires both arithmetic means to
exceed 100.

Important historical identity: the retained config set
`LLAMA_SPEC_PROFILE=0`, but this source uses `getenv()` presence semantics.
Therefore profiling was actually **enabled** in both recorded canonical runs.
The script preserves that behavior for an exact replay. The old filename
containing `noprofile` is historical and incorrect.

## 7. Replay the cold 15-prompt gate

```bash
repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/run-realistic-suite.sh \
  /new/results/muse-realistic
```

This runner sanitizes experimental environment variables, selects ARGMAX
explicitly, leaves `LLAMA_SPEC_PROFILE` absent, runs each frozen prompt once,
checks 15/15 measurable first-100 windows and `cached_tokens=0`, computes the
conventional `99 / (timestamp[99]-timestamp[0])` metric, and reproduces the
200,000-resample prompt bootstrap with seed 20260813. It stops the server before
hashing the final log.

For an additional no-spec/spec check against a running endpoint:

```bash
repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/check-parity-against-endpoint.sh \
  http://127.0.0.1:19494 /new/results/parity.json 256
```

The preserved ARGMAX evidence expects code and JSON to be exact at 256 while
prose takes the documented target-approved near-tie path. TOP_K reference and
1024-token code artifacts are also retained for audit.

## Expected results and interpretation

See [`manifests/expected-result.json`](manifests/expected-result.json) and the
[promoted result packet](../../results/muse-glimmer-30b-q8-woq-b70/README.md).
Normal variance is expected; a result is not comparable unless models,
hardware, TP/concurrency, flags, prompts, cache state, token counts, and metric
accounting all match. Report prose separately: it measured only 71–72 tok/s in
the canonical packet, and full-natural realistic median was 68.586 tok/s.
