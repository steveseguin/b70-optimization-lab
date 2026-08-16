# Local target-only graph validation — 2026-08-16

## Outcome

The exact pinned GPTQ model and vLLM XPU image ran successfully on one ASRock
Arc Pro B70. Enabling XPU graph at the contributor's scheduler and memory
settings improved the five-run p512/g128 median from **25.4184194017 tok/s**
in eager mode to **33.6902602058 tok/s**, a **32.5427%** gain.

This locally verifies the core target-only optimization and slightly exceeds
the contributor's provisional 32.9 tok/s claim. It does **not** reproduce the
contributor's unpublished prompt set, 230 W power policy, 131K context, MTP,
or quality claims.

## Identity and safety envelope

- Model revision: `9d189a60e4c0ad7f9f47cd94bfa393ca10b3924e`
- Image digest: `sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`
- vLLM: `0.27.2rc1.dev77+gac7509e2b.xpu`
- XPU kernels: `0.1.12.3`
- Device: one ASRock Intel Arc Pro B70 via `ZE_AFFINITY_MASK=0`
- Context: 8,192; scheduler: 64 sequences / 8,192 batched tokens
- Target: GPTQ INT4 symmetric G128; `desc_act=false`
- KV cache: FP8; prefix caching disabled; no speculation
- Host cgroup: 8 GiB memory / 10 GiB memory+swap
- Power: unchanged; no hwmon writes
- Both runs: exact 512-token prompts, 128 generated tokens, `--ignore-eos`,
  one shape warmup, five measured requests, cache counters zero

The graph run selected `XPUwNa16LinearKernel`, compiled one `(1,8192)` range,
captured 19 piecewise and 11 full decode graphs, and used 1.80 GiB for graph
memory. vLLM reported 16.59 GiB model memory and 7.56 GiB KV cache at U=0.90.

## Results

| Lane | Median decode | Mean | Min | Max | p-stdev | Median TTFT input rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| eager, U=0.75 | 25.418419 | 25.423634 | 25.382138 | 25.479844 | 0.031719 | 1730.247 tok/s |
| XPU graph, U=0.90 | **33.690260** | 33.691220 | 33.686637 | 33.698090 | 0.003965 | 1971.627 tok/s |

The contributor's exact prompt file and four-mode wrapper are not public.
This replay used six newly generated prompts from the copied public generator:
one same-shape warmup plus five unique measured prompts. Therefore the local
33.69 and reported 32.9 are compatible measurements, not an exact raw replay.

## Output parity gate

Greedy visible output was byte-identical for all five eager-versus-graph
request pairs. The SHA-256 values below cover `reasoning_text`, a NUL separator,
and `content_text`:

```text
ffaa8217659092b4c6d1b40f540e977bde1e37c3c16e995d30237a0effea8652
c914689790e8d0570ae3fa9ee3e20a9df6ccdeea982a83f22c42a251839002bc
80f8b9f2ac8f877494afd6bd8f2c72f89c46293cba9444f1502c06ab245f0b95
5fc9cf1d9103adfe313b14888649a0e6a41ffaaa2af6362d846e945f0e10dc5e
3611b0f525f86f702aac60fea648b54f7be25891986477869961128aaff17c9a
```

This establishes graph/eager behavioral parity for these five truncated
greedy samples. It is not a semantic quality evaluation, and both lanes use
FP8 KV. FP8 KV remains a separately labeled quality class from FP16 KV.

## Negative result retained

The first graph attempt used U=0.75 while retaining 64 scheduler slots. It
failed closed before graph capture because only 61 Mamba cache blocks were
available:

```text
ValueError: max_num_seqs (64) exceeds available Mamba cache blocks (61)
```

No device fault, reset, or hang occurred. U=0.90 provided sufficient cache and
is the contributor's actual no-spec setting.

## Evidence hashes

Raw files remain outside Git under
`/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`.

```text
9a81a9127d88b9bf8c5134020a6ddd4834db84271fd8636aa9e2325332c64eb3  prompts-p512.json
d307692c757e0e1fef080f9f47e9c269ef2f88c23d3eb940b87aadc2b7bba2f7  nospec-eager-p512-g128-n5/results.json
ca7c1c7d36331f9004fea10a7dba5eec41f2ae72f6605cb14a86147bc09b8b99  nospec-graph-u090-p512-g128-n5/results.json
0047ece80554b5fbc84aee68ed65c8cef35c9a23828736a01e3a29216c0d3233  nospec-eager-server.log
f03c34991bd72a633092415caa6e2b67b7d9b1a2a636cce48aa590ff0132c2c8  nospec-eager-container-inspect.json
1427f49e110b4abb456437bec697e20185e022f52ffcebc877487941a866c2c2  nospec-graph-u090-server.log
a159af0d23279b93da91b2be70dd3e4a24b6ba1f0a8fc31d5893961cee9faad0  nospec-graph-u090-container-inspect.json
62ea8fa20e12daa3a03fff1f3395e445836c5c1df79c5d0d84c456ce8dfbfd52  nospec-graph-u075-failed-server.log
33cc9cc24e31338683ed2cd8e3fc4ca843e32a8cb91c0d6ac49536a14fd0be5e  nospec-graph-u075-failed-container-inspect.json
```

## Next gates

1. Compare FP8 KV with FP16 KV using the same fixed prompts.
2. Inspect loaded MTP parameter dtype, then test MTP1 before deeper drafts.
3. A/B the nightly patch off/on; static source review says it is redundant for
   this exact model revision.
4. Increase context only after short-context MTP correctness and memory pass.
5. Do not copy the contributor's 230 W hwmon write without a separate,
   card-resolved power-policy study.
