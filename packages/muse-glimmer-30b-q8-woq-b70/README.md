# Muse-Glimmer 30B Q8/WOQ — four-B70 candidate package

This package is the human front door for the lab's four-card Muse-Glimmer
result: a `UD-Q8_K_XL` target, locally reconstructed BF16 DFlash assistant,
and a patched native llama.cpp/SYCL runtime. The two canonical full-256 runs
measured `100.088` and `100.649 tok/s`.

> **Status: expert candidate.** Source restore, build, model reconstruction,
> hashes, launch, and validation are present. The platform installer and an
> independent clean-host replay are not.

The [reproduction guide](../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
is authoritative. [`package.json`](package.json) is the machine-readable index.

## Who built what

**neural.download lab — integrated:** B70/SYCL bring-up, fixed-width oneDNN
Q8 WOQ, distributed argmax/local-winner reuse, DFlash integration, quality
gates, and this package. The preserved result and its limitations are in the
[result packet](../../results/muse-glimmer-30b-q8-woq-b70/README.md).

The published target and assistant checkpoints are pinned dependencies. No
separate speed uplift is assigned to them.

## Exact route

From the repository root, verify the preserved packet first:

```bash
python3 repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/verify-evidence.py
(cd repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813 && sha256sum -c SHA256SUMS)
(cd patches/muse-glimmer-30b-b70 && sha256sum -c SHA256SUMS)
```

Restore and build the exact source patch:

```bash
repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/restore-source.sh \
  "$HOME/src/llama.cpp-muse-q8-woq-repro"
LLAMA_CPP_ROOT="$HOME/src/llama.cpp-muse-q8-woq-repro" JOBS=2 \
  repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/build.sh
```

Download/reconstruct the two models. The helper fails unless both final GGUF
hashes match:

```bash
LLAMA_CPP_ROOT="$HOME/src/llama.cpp-muse-q8-woq-repro" \
  repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/download-models.sh \
  /path/to/muse-models
```

After stopping every other GPU workload, run the combined server and cold
15-prompt gate:

```bash
export LLAMA_CPP_ROOT="$HOME/src/llama.cpp-muse-q8-woq-repro"
export MUSE_TARGET_MODEL=/path/to/muse-models/Muse-Glimmer-30B-UD-Q8_K_XL.gguf
export MUSE_DRAFT_MODEL=/path/to/muse-models/dflash-bf16.gguf
repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/scripts/run-realistic-suite.sh \
  /new/results/muse-realistic
```

The runner owns startup, `/health`, benchmarking, teardown, and final hashes.
Do not compare only the `161.900 tok/s` cold first-100 median: full-natural
completion median was `68.586 tok/s`, and not every prompt exceeds 100.

## Certification gaps

The original complete draft-input identity was not retained, so the final
draft GGUF hash is the fail-closed boundary. A clean Ubuntu driver/toolchain
installation and beginner recovery flow remain to be tested.
