# B70 Model Packages

This directory is the user-facing packaging layer over verified material in
`repro/`, `results/`, and `patches/`. A package is a small, machine-readable
front door: it names exact hardware, model, runtime, patches, commands,
evidence, and any remaining gates without duplicating their source of truth.

A package status matters:

- `candidate`: useful on a matching expert-managed host, but one or more
  portability or clean-host gates remain;
- `starter`: clean-host replayed and eligible for an “Install guide” label;
- `preview`: intentionally unverified on the named platform, such as future
  Windows work.

The first package is the
[`Qwen3.8 27B official FP8 two-B70 candidate`](qwen38-27b-fp8-tp2-b70/).
It is not yet a starter package because the host Intel driver/Docker install
path has not been rebuilt and tested from a clean OS.

Package manifests are checked by `python3 tools/validate-repro-guides.py`.
The linked reproduction guide remains authoritative for technical details and
evidence; package files must point inward to it rather than becoming a second,
drifting recipe.
