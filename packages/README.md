# B70 Model Packages

This directory is the user-facing packaging layer over verified material in
`repro/`, `results/`, and `patches/`. A package is a small, machine-readable
front door: it names exact hardware, model, runtime, patches, commands,
evidence, and any remaining gates without duplicating their source of truth.
The `library` block supplies normalized discovery fields for the public guide
browser (family, quant, card count, OS, native/container delivery, use cases,
and measured metric). The `contributors` block records the exact work and
evidence carried into that package; upstream dependencies are not treated as
contributors unless a concrete contribution was adopted.

A package status matters:

- `candidate`: useful on a matching expert-managed host, but one or more
  portability or clean-host gates remain;
- `starter`: clean-host replayed and eligible for an “Install guide” label;
- `preview`: intentionally unverified on the named platform, such as future
  Windows work.

Current packages:

- [`Gemma 4 26B A4B Q8 one-B70 reconstruction candidate`](gemma4-26b-a4b-q8-b70/):
  our exact aggregate record-source snapshot, pinned target/F16-draft objects,
  local Q4_0 draft reconstruction, and strict target-verified replay gate;
- [`Qwen3.8 27B Q4_K_M one-B70 candidate`](qwen38-27b-q4km-tp1-b70/):
  our patched llama.cpp/SYCL source stack, direct-verified GGUF, exact-output
  benchmark gate, and a complete restore/build script;
- [`Qwen3.8 27B official FP8 two-B70 candidate`](qwen38-27b-fp8-tp2-b70/):
  digest-pinned vLLM XPU baseline.

None is a starter package yet because its host platform path has not been
rebuilt and tested from a clean OS. Gemma additionally lacks the retained
historical server and local Q4_0 draft hashes, so it is explicitly a source
reconstruction candidate.

Package manifests are checked by `python3 tools/validate-repro-guides.py`.
The browser reads the generated [`catalog.json`](catalog.json), which must not
be edited by hand. After adding or changing a package, rebuild and validate it:

```bash
python3 tools/validate-repro-guides.py --write-package-catalog
```

The linked reproduction guide remains authoritative for technical details and
evidence; package files must point inward to it rather than becoming a second,
drifting recipe.
