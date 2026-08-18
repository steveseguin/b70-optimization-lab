# Maintainer audit of bosd PRs #30–#33

Date: 2026-08-17 (America/Toronto)

This is a narrow maintainer normalization of four community reports. The
contributor text remains preserved; editor notes distinguish reported claims,
source-verified facts, and reference-lab measurements.

## Summary

| PR | Maintainer disposition |
| --- | --- |
| #30 | Reported arithmetic is correct, but the comparison does not isolate the backend because model, architecture, quantization, MTP head, and runtime also change. |
| #31 | Image support and checkpoint MTP structure verified; +55% remains community-reported. Draft-path and TP2 root-cause explanations are hypotheses. |
| #32 | Checkpoint failure observations retained; the claim that public b3.1 lacks an XPU quantized-MoE kernel is corrected. |
| #33 | Configuration reproduced safely. The 84–97 tok/s range was workload-favorable and did not generalize to the fixed realistic suite. No functional quality failure was found. |

## PR #33 reproduction fidelity

The lab used the same performance-critical shape claimed by the report:

- Qwen3.8-27B Q4_K_M target, 18,973,870,432 bytes, SHA-256
  `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`;
- Q4_0 MTP draft, 1,680,271,648 bytes, SHA-256
  `051a1764cff8c4f3ee6ae8b00593a0364c7539c67fa50ffc58f3f96509fca38e`;
- two B70s, `--split-mode tensor`, 1:1 tensor split, flash attention, F16
  target/draft KV, context 8192, parallel 1, `draft-mtp` n-max 8;
- batch and ubatch 8192, cache RAM and context checkpoints disabled, greedy
  requests, 512 output tokens; and
- `UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1` with the accepted TP2 optimization
  family derived from `mndodd/llama.cpp @ 4302fb599` and the 0xSero patch stack.

The executable was the lab's later same-family TP2 build, SHA-256
`6ae782c7e8f7a992e0eeced10ade2a84b3cbb9ba65c65cbb917e52d1ce09777d`;
its SYCL library SHA-256 was
`375f6d251b022b62367e73d2cd6b7eb0200efc9cc9c854a509af45950938c3ed`.
It includes additional target-side lab optimizations, so this was not an older
or intentionally disadvantaged control. It is not a byte-identical build of
the contributor's container, which is why the result is classified as a
same-configuration-family reproduction rather than an exact binary replay.

The test was more representative than the report's favorable-prompt timing:
12 unique fixed prompts, each sent once, `cached_tokens=0` for every request,
no response/history reuse, and a matched MTP-off control under the same binary
and server settings. The conventional external full-response metric was also
checked against `llama-server` timing.

## Results

| Mode | first 100 after TTFT median | full after TTFT median | wall median | server full median |
| --- | ---: | ---: | ---: | ---: |
| TP2 target-only | 48.82 tok/s | 48.38 tok/s | 47.56 tok/s | 48.43 tok/s |
| TP2 MTP8 | 46.23 tok/s | 43.45 tok/s | 42.72 tok/s | 43.44 tok/s |

MTP8 full-response throughput was 10.2% below the matched target-only control.
Its first-100 rate ranged from 34.30 to 81.14 tok/s. Draft acceptance was
workload-dependent, with mean acceptance ratio 0.259 and average accepted
length 3.06. The single favorable 81.14 tok/s row explains how a prompt-selected
headline can approach the contributed range, but the 84–97 tok/s claim did not
generalize.

The server reported CPU-sampler fallbacks for tensor-split target and draft
sampling. They did not prevent correct execution, but their performance effect
was not separately A/B tested.

## Quality and safety

Seven exact-answer/JSON/code canaries, eight identical-repeat checks, and a
3,829-token requested long-context needle (3,582 actual prompt tokens) all
passed and matched the known target baseline. The 12 long-form MTP outputs were
not hash-identical to the target-only outputs, so this establishes functional
canary parity, not full bit-exact or benchmark-suite quality equivalence.

The run used a bounded user memory scope on the 16 GB host. It produced no GPU
fault, reset, kernel error, panic, or OOM. No PCIe ASPM, runtime-power, device
reset, firmware, driver, or kernel-policy setting was changed.

## Local evidence hashes

Full raw files remain outside Git under
`/mnt/fast-ai/bench-results/bosd-pr33-audit-20260817/`:

- MTP8 realistic summary: `09011d78e5456fd09ecc816abe707dee56ebb7b8e537228dab8c485e88c72f62`;
- target-only realistic summary: `5636d74fe5052bb11e312d0e2110fc1c19173d905eccdebe3976f96be108c0b9`;
- full quality result: `0371c35143a24686346b66a31325f578a664f7412478c321abb581edb3f5c8e1`;
- MTP8 server log: `200396464a567174437e9d01596b7f8cc4dd4efd773f59e2c8dd091199eb33d1`;
- target-only server log: `f9674d4e047b380909f99901e5000d4a50243450e1af0a4a18eb91f9e51182da`.

## Source checks

- The contributor's pinned snapshot
  [`64df816d`](https://github.com/bosd/trx50-arc-b70-benchmarks/tree/64df816d5546b8a7f2d99a6524fc9e4155dc7908)
  contains the PR #30 narrative but not raw logs supporting PRs #31–#33.
- The reviewed 0xSero snapshot is
  [`17323a6b`](https://github.com/0xSero/qwen38-b70/tree/17323a6b8948a7b4483633e24ba796df0fdb43a9).
  Its older entrypoint uses obsolete MTP arguments; current llama.cpp requires
  `--spec-type draft-mtp` and `--spec-draft-n-max`.
- The exact Intel b3.1 image inspected for PR #32 reported vLLM
  `0.21.1.dev0+gad7125a43.d20260812` and torch `2.11.0+xpu`. Its source includes
  XPU INT4 fused-MoE classes, contrary to the report's universal no-kernel
  inference. Intel's
  [public reference commands](https://github.com/intel/llm-scaler/blob/main/vllm/README.md#32-reference-commands-for-running-the-supported-qwen3536-models)
  also document `sym_int4` for supported Qwen3.5/3.6 MoE models.
