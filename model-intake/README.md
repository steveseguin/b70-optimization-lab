# Model Intake Queue

This directory is the lab-owned inventory of models worth acquiring for
independent B70 testing. It is intentionally not a mirror of somebody else's
cookbook. Outside reports can identify a family worth testing, but the model
identity, local result, patches, and final recipe are established here.

The current catalog is [`catalog.json`](catalog.json). Every downloadable
artifact records an immutable repository revision, exact filename, byte count,
publisher checksum, intended B70 card count, license state, and why it belongs
in the queue. Popularity figures are a dated Hugging Face API snapshot and are
only a discovery signal.

## Current First Wave

| Priority | Artifact | Size | Why |
| --- | --- | ---: | --- |
| 1 | Ornith 1.5 35B A3B Q4_K_M | 20.22 GiB | New official family, highly trending, and overlaps an unverified external one-B70 claim. |
| 2 | Ornith 1.5 9B Q8_0 | 8.87 GiB | Recent official single-card model suitable for a beginner recipe. |
| 3 | Nemotron 3.5 Lightning 30B A3B UD-Q4_K_M | 23.53 GiB | Enables independent family-claim validation without assuming NVIDIA NVFP4 works on Intel. |
| 4 | LFM2.5 2.6B Q8_0 | 2.68 GiB | Small, popular, and inexpensive to keep as a novice lane. |

Total first-wave download: **55.30 GiB**. DeepSeek V4 Pro 0813, Qwen3.8
2.4T-A95B, and Ling 3.0 tiny remain watch entries because storage or current
XPU runtime support makes a download premature.

Qwen3.6-35B-A3B, Muse-Glimmer-30B, and Qwen3.8-27B are explicitly listed as
already covered. A new outside report for one of those families is not, by
itself, a reason to duplicate its weights or change recipe provenance.

## Safe USB Workflow

The external drive is expected at `/mnt/usb-models`. It does not auto-mount.
Mount it and check its health according to
[`docs/reference-lab-storage.md`](../docs/reference-lab-storage.md), then run:

```bash
python3 scripts/model-intake.py list
python3 scripts/model-intake.py plan --root /mnt/usb-models
python3 scripts/model-intake.py init-store --root /mnt/usb-models
python3 scripts/model-intake.py download --root /mnt/usb-models --all-queued
```

`init-store` is one-time. It refuses the OS filesystem, a subdirectory that is
not itself a mount root, a read-only mount, and a non-USB transport by default.
`download` also requires the store marker and reserves 100 GiB after the
planned artifacts. Do not use `--allow-non-usb` merely to bypass a refusal; it
exists for an explicitly reviewed external enclosure whose transport cannot be
reported correctly.

Downloads resume into `.part` files. Promotion to the runnable filename only
happens after the exact byte count and SHA-256 match. The final artifact is
then hashed through both direct I/O and the ordinary page-cache path. If the
filesystem cannot provide either direct mode, verification fails closed.

Download one entry instead of the complete wave with:

```bash
python3 scripts/model-intake.py download \
  --root /mnt/usb-models \
  --id ornith-15-35b-a3b-q4km
```

Drive-local manifests and verification reports are written under
`/mnt/usb-models/.b70-manifests/`; a small `.intake.json` identity sits beside
each promoted model file. Tokens are read from the existing private Hugging
Face token file and are never placed on the command line.

## From Download To Project Recipe

Downloading is not validation. Each new model proceeds through these states:

1. `queued` — immutable artifact selected and storage budget approved.
2. `downloaded` — exact bytes and direct/ordinary identity verified.
3. `bring-up` — clean upstream runtime starts on the intended one- or two-card
   topology; failures are preserved.
4. `baseline` — fixed cold suite, quality gate, and no-cache control recorded.
5. `optimized` — project patches tested against the baseline with matched A/B
   evidence.
6. `packaged` — an in-repo novice recipe, and later a tested container or
   Windows packet, points back to the verified result.

An external patch receives precise credit when its identifiable delta survives
that process and improves the matched lab lane. An external performance report
that merely prompted the test remains an acknowledged lead, not the source of
the lab's recipe or optimization history.

