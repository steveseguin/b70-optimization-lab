# Canonical Q8 Phase-2 crossover: sealed no-effect result

Date: 2026-08-10

## Classification

The corrected two-wave, four-card, same-card selector crossover completed and
was independently audited `GO`. Its preregistered scientific classification is
`NO_EFFECT`: all four selector-on lanes and all four selector-off lanes
reproduced the known heterogeneous-c2 forced-tail landmarks, with no mismatch
before the separately measured natural-answer boundaries. The canonical
single-column MMVQ plus recurrent-output DMMV control therefore did not repair
this behavior, and this source lane is closed.

This remains `diagnostic-only`, `performance_promotable=false`. It suppresses
EOS to force 512 tokens and makes no natural-stop, latency, fairness, aggregate
rate, or performance claim.

Sealed packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c2-crossover-four-gpu-20260810T040016.211980985Z`

- exhaustive root artifact-manifest SHA-256:
  `b38abbb3046699f50f4631cb92fa2347aae937435e2c7a1450f5fba5848540cb`;
- crossover-summary SHA-256:
  `5c99fa0b35a8bbaad1e752f41b0037f00d7ee872da7922791256c0de891e1bdf`;
- detached completion-marker SHA-256:
  `2b01c13940122ad723ebd46c7b2f49d56ea7e34d2f4b9b5566b0b274be98c3b1`;
- root status: `EVIDENCE_VALID`, cleanup `PASS`, no forced kill or cleanup
  survivor;
- both wave manifests and all eight lane manifests are sealed inside the root
  manifest, which verifies in full.

## Crossover result

The physical-card mapping was held constant while each card flipped the
selector between waves:

- GPU 0 and GPU 1 ran forward A0/B1;
- GPU 2 and GPU 3 ran reverse B0/A1;
- wave 1 used selector off/on/off/on;
- wave 2 used selector on/off/on/off.

Every forward lane kept A/slot 0 exact for all 512 generated tokens. Every
forward B/slot-1 stream first differed from its matched c1 oracle at generated
token 71 (`332` observed versus `71093`), immediately after B's separately
measured 70-token natural answer. Every reverse lane kept B/slot 0 exact for
all 512 tokens. Every reverse A/slot-1 stream first differed at generated token
96 (`90` observed versus `71093`), immediately after A's separately measured
95-token natural answer. Thus all eight lanes reproduce B71/A96 and none shows
a pre-boundary quality regression.

Selector-on lanes retained the required flat prerelease and recurrent
post-release route markers; selector-off lanes retained no canonical route
markers. Both waves proved true M2 occupancy, correct card/port/process/runtime
binding, exact input hashes, cache-zero capture, and clean teardown.

`NO_EFFECT` does **not** mean the complete forced tails were equal between
selector states. GPU 0's forward B/slot-1 tail had token-array SHA-256
`80bf67bda3e640d6b27a85422154f7a9d018a7f25dc604400eb7e4e4ea9af43c`
with the selector off in wave 1 and
`de9f6f1f4f43c379426f061958e0047cdf8510dd13999b2b65adc9e667c671b9`
with it on in wave 2. Both share the preregistered B71 landmark, which is the
classification endpoint. Later forced-tail hashes are not causal endpoints,
so no full ON/OFF output-equality claim is made.

## Decision

Do not spend another live wave separating canonical recurrent DMMV from
single-column reordered MMVQ: the combined control activated exactly and had no
effect on the relevant boundary. Preserve the default-off code and this
negative result. Resume the measurable prompt-processing/decode frontier; keep
the separately required synchronized natural-stop c2 and naturally sustained
512-token serving checks on the scorecard.
