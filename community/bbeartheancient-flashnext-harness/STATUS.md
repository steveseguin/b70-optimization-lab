# STATUS — bbeartheancient Qwen3.8 Flash-Next llama.cpp harness

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | complete static read and clean apply check; no contributed code executed |
| Tested in reference lab | no |
| Safe to merge as documentation | yes, with the claim limits below |
| Eligible for `repro/` or `results/` | no |

## Provenance

- Contributor: [`bbeartheancient`](https://github.com/bbeartheancient).
- Source: [`flashnext-harness`](https://github.com/bbeartheancient/flashnext-harness).
- Reviewed commit:
  [`138cb88f326587d1cd9776510b2db0bd6a35455b`](https://github.com/bbeartheancient/flashnext-harness/commit/138cb88f326587d1cd9776510b2db0bd6a35455b).
- License: MIT.
- llama.cpp base: `9723942adc518b43c4b95dc4dce6906903eb5e09`.
- Published patch SHA-256:
  `bf9b00b89cf132c6db95bd51f7f3398b5362986c7c116e083631ac9cec8972b1`.

## Contributor Claim

The repository reports approximately `20 tok/s` warm generation and
`50 tok/s` prompt processing on two B70s for a llama.cpp lane using Q8 core
weights, Q4_K_M experts, Q6_K PLE, CPU/NVMe offload, and a 48K service cap.
This is not the official FP8 model identity and is not a reference-lab result.

## What Was Actually Run Here

No model conversion, contributed binary, Python helper, server, GPU workload,
or benchmark was run. The complete relevant source, patch, recipe, launch
script, PLE probe, and license were read in an isolated clone. The published
patch applies cleanly to its declared llama.cpp base under `git apply --check`.

## Findings

1. No inference kernel is transferable to the lab's official FP8 vLLM lane.
   The repository's optional FWHT, QK-int8, dequantization, and RTU kernels are
   standalone latent-lane tools and are not connected to the measured
   llama.cpp Flash-Next path.
2. Static whole-decode execution is the useful conceptual overlap. The lab
   independently established it first for this FP8 lane in A44, improving the
   protected eager median from `5.515783` to a diagnostic `20.507849 tok/s`.
   No external patch is imported or boost credited for that lab-developed
   result.
3. The patch is a useful independent MTP semantic cross-check: the draft uses
   the pre-mix hyperconnection-wide target state, separately projects token
   embedding and target hidden state, runs dense attention without PLE/QSA
   indexer state, and shares trunk embedding/head. The current vLLM lane
   already follows the broad structure, so this is an oracle, not a speed
   patch.
4. The placement principle—keep frequently used experts resident—is sound,
   but the implementation's Q4 experts, Q6 PLE, CPU layers, and NVMe misses
   change model quality and are outside the official-FP8 lossless contract.

## Known Issues

- No benchmark logs, structured result, output hashes, quality battery, model
  checksum, GGUF checksum, repeat distribution, or exact metric definition is
  published for the approximately 20 tok/s claim.
- The measured runtime is described as an uncommitted working tree, so its
  exact source identity is not reconstructable from the clean patch alone.
- `data/ple_probe.json` is referenced but absent. The probe implements q4,
  INT4-group-128, and INT8 only; it cannot generate the documented q5/q6
  ladder, depends on an unprovided `/tmp/fn_bf16_index.json`, and reads a
  mutable Hugging Face `main` revision.
- The README advertises MTP support, while the measured recipe says MTP was not
  exported and remained unconfirmed.
- The 48K context configuration has no published long-context retrieval or
  end-to-end quality evidence; row-level PLE SQNR is not a losslessness gate.

## Disposition

Keep this as a `community-reported` static review. Port no code into the active
FP8 runtime. Retain the MTP structure as a correctness cross-check and the
static-graph observation as independent conceptual support, while optimizing
the bottlenecks measured by the lab's own A28 profile. No claims-registry entry
is created because the reported performance identity is incomplete.
