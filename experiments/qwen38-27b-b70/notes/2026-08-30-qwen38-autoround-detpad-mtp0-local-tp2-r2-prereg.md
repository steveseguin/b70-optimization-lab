# Qwen3.8-27B AutoRound INT4 deterministic MTP0 local TP2 r2 preregistration

Date: 2026-08-30
Status: frozen before the first r2 model request

## Delta from r1

R1 failed before server launch, model loading, or any request. Direct and
ordinary model verification passed 19/19, then the marker preflight falsely
failed because `grep -q` closed a `strings` pipeline early under `pipefail`.
The result is preserved in
`../data/2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r1-result.json`.

R2 changes only that shell preflight (and the analogous bounded container/port
queries) to consume their complete input. It uses new evidence and cache roots.
No model, image, kernel, treatment, prompt, metric, ordering, or pass criterion
changed.

## Frozen identity and treatment

- host `steve-TURIND8-2L2T`, GPUs 0 and 1, TP2;
- local ext4 model
  `/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround`;
- model-manifest SHA-256
  `731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8`;
- image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- kernel source `1e90ffa672ba02f17a909da11838a4c55b199783`, patch
  `8237fd2a5f11c772269275598bc005d7a146f86de741cef753fc0ec74cb1a408`;
- wheel
  `823615350c5344532f63dde8652b291d7b9d6815a209121c97f2fcfac09474c5`;
- XPU extension
  `c5e9c9a505f64e0e4be819191ef091c09bfb2af153c6c7c341c80e8ebed2e620`;
- GDN library
  `2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355`;
- AutoRound/INC W4A16, FP16 activation/KV, MTP0, deterministic Inductor,
  XPU Graph off, `cudagraph_mode=NONE`, persistent GDN scratch, explicit oneCCL
  completion, prefix caching off, temperature 0, seed 42, one sequence;
- 12-prompt/six-class suite
  `df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac`,
  natural EOS, complete token IDs, and cached tokens required to be zero;
- final-image operator qualification remains 0/200 mismatches at all ten M
  values and 0/500 padded instability, as recorded in
  `../data/2026-08-30-qwen38-autoround-detpad-operator-r3.json`.

## Ordered gates

1. Fresh eager MTP0 oracle.
2. Fresh compiled A only after eager passes every workload and canary gate.
3. Compiled A must be 12/12 token-array exact to eager before fresh compiled B.
4. Qualification requires compiled A and B each 12/12 exact to eager and exact
   to each other.

Every arm must pass direct model and image identity checks, INC detection, both
TP workers, no graph capture, all 12 rows, natural EOS, class-balanced median
over intervals 1--100 after TTFT, zero cached tokens, canaries, cleanup, and no
new GPU/kernel/OOM fault. On any failure, stop and preserve evidence. Passing
qualifies only the deterministic MTP0 parent; it does not validate MTP,
concurrency, long context, aggregate throughput, or a public speed.

R1's full question, exclusions, and anti-cheating rules are incorporated from
`2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r1-prereg.md` without
relaxation.

Executable:

- `../scripts/run-20260830-qwen38-autoround-detpad-mtp0-local-tp2-r2.sh`
