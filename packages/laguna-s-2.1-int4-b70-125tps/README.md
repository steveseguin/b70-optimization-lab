# Laguna S 2.1 INT4 — four-B70 record replay package

This package indexes the lab's artifact-exact Laguna record: INT4 target and
DFlash models, BF16 KV, TP4+EP4, exact M12 verification, one active request,
and `125.461973 tok/s` conventional median.

> **Status: originating-host lab replay.** This is not a portable installer.
> The exact source bundles, native hashes, runtime lock, launcher, and sealed
> evidence exist; a clean source rebuild and non-originating-host replay do not.

Read the [record guide](../../repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md)
and [qualified result](../../results/laguna-s-2.1-int4-b70/README.md) before
changing any identity field.

## Who built what

**neural.download lab — integrated:** Laguna B70 bring-up, the exact M12
verifier and DFlash path, the shared-elementwise optimization, provenance
locks, quality/idle gates, and packaging. The promoted change moved the
conventional median from `124.642413` to `125.461973 tok/s` (`+0.6575%`) with
13/13 exact prompts and zero cached tokens.

## Exact route

First audit the portable predecessor packet and both record bundles without
running a model:

```bash
repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-record.sh
git bundle verify patches/laguna-s-2.1-xpu-b70/vllm-laguna-shared-elementwise-m12-1a7f61fef-20260731.bundle
git bundle verify patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-shared-elementwise-m12-99886d783-20260731.bundle
```

The older portable packet contains the model acquisition and source-restore
machinery shared by this lane:

```bash
repro/laguna-s-2.1-int4-b70-102tps-20260726/restore-models.sh \
  --download /path/to/laguna-models
repro/laguna-s-2.1-int4-b70-102tps-20260726/restore-sources.sh \
  /path/to/laguna-sources
```

Those helpers do not turn the 125 tok/s record into a portable build. On the
originating host, with the record-specific worktrees and locked native
artifacts already in place, run exactly one gate:

```bash
repro/laguna-s-2.1-int4-b70-125tps-20260731/run-record-gate.sh
```

The gate owns launch, health, the one cold 13-prompt suite, exactness checks,
cache-zero checks, pre/post idle evidence, and teardown. Do not retry to select
a faster start.

## Certification gaps

The missing work is explicit: a record-specific portable build helper,
platform installation, clean-host model acquisition, non-originating-host
replay, and beginner recovery. Until those pass, the guide library must label
this a lab replay, not an install guide.
