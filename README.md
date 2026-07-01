# B70 Optimization Lab

Practical recipes, patches, result packets, and lessons for making local LLM
inference work well on Intel Arc Pro B70 / Battlemage hardware.

This is Steve Seguin's public lab notebook. It is not a generic benchmark
landing page: the goal is to show what B70s can run, how the fast paths were
built, and which results are reproducible enough to trust.

## What This Helps With

- Run useful models on B70 hardware instead of guessing from scattered posts.
- Compare realistic tok/s ranges for MiniMax, Gemma, Qwen, and related lanes.
- Pull model-specific vLLM, llama.cpp, SYCL, and kernel ideas into upstream work.
- Reproduce records without accidentally counting cache, stale AOT, or invalid
  speculative output as speed.
- Use the repo as a template for agent-driven model optimization on local GPUs.

Some wins here are too model-specific to become clean upstream patches as-is.
The repo still makes them useful: exact commands, caveats, failure notes, and
patch evidence are preserved so humans and AI agents can extract the general
parts later.

## Fast Paths

- Deploy a useful 4x B70 endpoint:
  [MiniMax fresh Ubuntu 24 deploy](repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md)
- Browse model-specific setup and result recipes:
  [Model recipes](docs/model-recipes.md)
- Find the full artifact map:
  [Current reproducibility map](docs/current-reproducibility-map.md)
- Inspect the top MiniMax structured result:
  [MiniMax structured `94.406 tok/s` recipe](repro/minimax-m27-b70-94tps-structured-20260522/README.md)
- Inspect the Gemma 26B record identity:
  [Gemma 26B Q8 record identity note](repro/gemma4-26b-a4b-q8-b70-current-20260701/README.md)
- Review Qwen3.6 35B validity lessons:
  [Qwen3.6 35B result packet](results/qwen36-35b-quark-int8-b70/README.md)
- Check local credentials and submission rules:
  [Local ops](docs/local-ops.md) and [LocalMaxxing notes](docs/localmaxxing.md)

## Headline Results

These are pointers, not apples-to-apples claims. Throughput depends on model,
quantization, prompt/output shape, context, concurrency, cache policy, and
engine identity.

- Gemma 4 26B A4B Q8 target + Q4_0 MTP draft:
  `124.98 tok/s` verified short-decode record on one B70, up from a
  `74.30 tok/s` no-spec control.
- Gemma 4 12B INT4 service:
  `780.97 tok/s` aggregate at c8 for practical 32K text+image serving.
- MiniMax M2.7 INT4 AutoRound:
  `83.17-94.41 tok/s` across deployable, strict, and structured 4x B70 lanes.
- Qwen3.6 35B Quark INT8:
  `93.55 tok/s` strict current baseline, with benchmark-identity lessons.
- Qwen3.6 27B Q4_0 / FP8:
  `50.13 tok/s` Q4 and `49.58 tok/s` FP8 from source-level runtime work.
- MiniMax M2.7 GGUF UD-IQ4_XS:
  `17.70 tok/s` on the valid llama.cpp RPC/SYCL path.

## How To Read This Repo

- If you are a B70 owner, start with the recipes and deployable MiniMax path.
- If you maintain vLLM, llama.cpp, Intel XPU, oneAPI, or kernels, jump to the
  detailed evidence sections and patch/result folders.
- If you are optimizing a new model, copy the workflow: define the metric, lock
  the run identity, gate quality, save failed attempts, then promote only
  reproducible wins.
- If a number looks surprisingly fast, read its caveat before comparing it to
  another GPU or another LocalMaxxing row.

The sections below are intentionally denser. They keep enough detail for
reproduction, upstream mining, and future optimization agents.

<details>
<summary><strong>Detailed Decode Scorecard</strong></summary>

## Decode Scorecard

All headline numbers below are generated/output-token throughput unless a row
explicitly says aggregate, total, or prompt/prefill. Do not compare rows unless
model, quantization, prompt/output shape, context, concurrency, quality gate,
and runtime identity match.

| Model / lane | Best current decode result | Prefill / context notes | Started from or control | Repro / details |
| --- | ---: | --- | --- | --- |
| Gemma 4 26B A4B Q8 target, Q4_0 MTP draft | `124.977 tok/s` median generated tokens 1-100 after TTFT on the fixed cold realistic suite, `cached_tokens=0`, LocalMaxxing `cmr1u77na01k2ld01kalwzs1e` | 32K context, f16 KV. Long-context service prefill with the GQA8 FlashAttention tile patch reached about `1.04K-1.08K prompt tok/s`; the near-30K case improved from `702.6` to `947.6 prompt tok/s`. | No-spec fixed-suite control: `74.297 tok/s` (`+68%` to the current record). Older `176+ tok/s` and `245-280 tok/s` rows are synthetic/warmed diagnostics only. | [Gemma current repro](repro/gemma4-26b-a4b-q8-b70-current-20260701/README.md) |
| Gemma 4 12B IT INT4 AutoRound | c8 production: `780.97 tok/s` aggregate at 8 concurrent 512-output requests; c1 single-generation check: `112.87 tok/s` | 32K text+image OpenAI-compatible endpoint, prefix caching, 8 active generations, fail-fast frontdoor. Near-30K repeated-prefix TTFT improved from `22.44 s` to `3.75 s`. | c1/c2/c4/c8 aggregate scaling at 512 output: `112.77`, `205.47`, `398.98`, `784.69 tok/s`. | [Gemma 12B experiment](experiments/gemma4-12b-int4-autoround-vllm/README.md) |
| MiniMax M2.7 INT4 AutoRound, constrained structured lane | `94.406 tok/s` effective accepted output, `94.692 tok/s` post-first, `30/30` accepted, `0` rejects, LocalMaxxing `cmphg048s00mppc0192sahyug` | 4x B70, vLLM/XPU TP4, context 4096, prefix cache on, structured regex2 HTML suffix. | Regex1 control had one rejected first attempt and `89.563 tok/s`; regex2 removed the loophole and raised effective accepted throughput by about `5.4%`. | [Structured repro](repro/minimax-m27-b70-94tps-structured-20260522/README.md) |
| MiniMax M2.7 INT4 AutoRound, strict random decode | `89.314 tok/s` output, `119.086 tok/s` total at p512/n1536, context 2048, LocalMaxxing `cmpct6t4m007fnw01yjdtlcs4` | Fresh Ubuntu 24 deployable endpoint is lower but more useful operationally: `83.17 tok/s` output / `110.90 tok/s` total, 32K served context, and about `1.7K-1.8K prompt tok/s` on endpoint prefill checks. | Early vLLM AutoRound bring-up was around `19.85 tok/s` at p512/n128; llm-scaler INT4 MoE, graph, allreduce, and MiniMax-specific fixes moved the lane into the `83-94 tok/s` band depending on benchmark shape. | [Strict repro](repro/minimax-m27-b70-89tps-20260520/README.md), [fresh deploy](repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md) |
| MiniMax M2.7 REAP AutoRound W4A16 | Best approved archived row: `89.499 tok/s` output, `119.332 tok/s` total, LocalMaxxing `cmpuesbma00r5mq01yk0zdcjx`. Current live-source quality-valid floor is lower, about `83.52 tok/s`. | 4x B70, vLLM/XPU TP4, p512/n1536. Smaller 85.23 GiB safetensor footprint than the Lasimeri checkpoint. | Conservative first pass: `87.71 tok/s`; CCL and pidfd IPC raised the archived best to `89.499 tok/s`. Later live-source changes made exact reproduction noisy, so keep the caveat attached. | [REAP repro](experiments/minimax-m27-reap-autoround-vllm/REPRO.md) |
| Qwen3.6 35B A3B Quark W8A8 INT8 | Current strict 4x B70 baseline: `93.5505 tok/s` corrected output, `178.773 tok/s` total client token rate. Legacy LocalMaxxing-approved row: `99.428 tok/s`, older gates. | vLLM/XPU TP4, Quark W8A8 INT8, 32K context, PIECEWISE forced-comm graph identity. TTFT mean on the deep gate: `187.34 ms`. | A graph-none run around `15 tok/s` was a benchmark-identity mistake, not a regression. Fast `107-198 tok/s` speculative artifacts failed canaries or were synthetic. | [Qwen35 packet](results/qwen36-35b-quark-int8-b70/README.md), [reproduce](results/qwen36-35b-quark-int8-b70/reproduce.md) |
| Qwen3.6 27B Q4_0 GGUF | `50.1299 tok/s` decode on 3x B70 with the quality-cleared fused beta/alpha GGUF and root-residual disabled, LocalMaxxing `cmov6p4r7007tqr01yi8ug4un` | Prompt throughput in the same p512/n512 run: `200.48 prompt tok/s`; total `80.20 tok/s`. | Clean single-B70 baseline was `24.723 tok/s`; the best 3x fused lane is about `2.0x` that single-card baseline. Equal 4x tensor split was negative (`34.929 tok/s`), while 3x beat 4x for latency. | [Q4_0 result notes](results/q4_0-gguf-2026-05-04-sycl-single-kernel-allreduce.md) and data ledgers |
| Qwen3.6 27B static FP8 | Best recorded FP8 lane: `49.582 tok/s` output with vLLM/XPU TP4 plus CPU n-gram speculative decode. Current refreshed no-spec TP4: `45.865 tok/s`; n-gram refresh: `48.082 tok/s`. | TP4/PP1 is the speed layout; TP2/PP2 fits 32K but drops to `27.722 tok/s`. | Initial official FP8 fallback was only `2-3 tok/s` before the later compressed-tensors path and vLLM/XPU improvements. | [FP8 result note](results/fp8-vllm-xpu-qwen36-2026-05-04.md) |
| MiniMax M2.7 UD-IQ4_XS GGUF | `17.698 tok/s` decode on 4x B70 RPC+SYCL layer mode; p512/n128 also reached `54.506 prompt tok/s` and `17.693 decode tok/s`. | llama.cpp RPC/SYCL, corrected RPC device mapping, fast IQ4_XS path, runtime MMV row packing, fused RMSNorm, merged gate/up experts. | Original process-per-GPU baseline was `13.754 tok/s`; current best is about `+29%`. Vulkan did not beat SYCL/RPC. | See MiniMax GGUF data and notes from 2026-05-07/08 in [notes/](notes/) and [data/](data/) |
| DeepSeek V4 Flash AutoRound | No promoted tok/s yet. | Initial research lane only. The checkpoint and vLLM code path were surveyed, but loader/runtime/quality gates are not past the first milestone. | Not eligible for LocalMaxxing. | [DeepSeek experiment](experiments/deepseek-v4-flash-autoround-vllm/README.md) |

External LocalMaxxing pages are useful for context, but their public model
boards can mix hardware, quantization, prompt shapes, and validation policies.
For example, the MiniMax AutoRound board lists a `94.5 tok/s` top row, which
matches this repo's structured MiniMax lane class, while the Gemma 26B public
board currently highlights lower-precision rows and is not an apples-to-apples
Q8-target comparison:

- <https://www.localmaxxing.com/en/models/Lasimeri/MiniMax-M2.7-int4-AutoRound>
- <https://www.localmaxxing.com/en/models/google/gemma-4-26B-A4B-it>

</details>

<details>
<summary><strong>Repro Folders And Evidence Map</strong></summary>

## What The Repro Folders Prove

| Path | What it reproduces | Important caveat |
| --- | --- | --- |
| [repro/gemma4-26b-a4b-q8-b70-current-20260701](repro/gemma4-26b-a4b-q8-b70-current-20260701/README.md) | Current Gemma 26B Q8-target fixed cold-suite record identity and command wrapper. | This is a record identity note until the full harness is imported into this branch; the wrapper checks for the missing harness and exits clearly. |
| [repro/minimax-m27-b70-94tps-structured-20260522](repro/minimax-m27-b70-94tps-structured-20260522/README.md) | MiniMax constrained simple-HTML fast lane using the compact public runner. | It is not unconstrained website generation. The grammar/scaffold is part of the benchmark identity. |
| [repro/minimax-m27-b70-110tps-ubuntu24-20260523](repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md) | Fresh Ubuntu 24 setup, model download, stack build, quality gate, and OpenAI-compatible 32K endpoint. | The score is the deployable 32K serving baseline, not the fastest MiniMax output-token row. |
| [repro/minimax-m27-b70-89tps-20260520](repro/minimax-m27-b70-89tps-20260520/README.md) | Older strict p512/n1536 MiniMax speed lane and quality gates. | Context is 2048 and the setup is more speed-focused than service-focused. |
| [results/qwen36-35b-quark-int8-b70](results/qwen36-35b-quark-int8-b70/README.md) | Closed Qwen35 result packet: valid baselines, invalid fast lanes, and reproduction commands. | Do not compare runs unless PIECEWISE graph and all identity fields match. |
| [experiments/gemma4-12b-int4-autoround-vllm](experiments/gemma4-12b-int4-autoround-vllm/README.md) | Production model-slot profile for Gemma 12B text+image serving. | This is a production/service profile, not a single-request LocalMaxxing-style short-decode record. |
| [experiments/minimax-m27-reap-autoround-vllm](experiments/minimax-m27-reap-autoround-vllm/REPRO.md) | REAP MiniMax bring-up, best archived result, and current caveats. | The best archived `89.499 tok/s` row is not currently reproduced by the live source with the same quality status. |

</details>

<details>
<summary><strong>Optimization Lessons</strong></summary>

## What Worked

| Lever | Where it helped | Typical observed gain | Notes |
| --- | --- | --- | --- |
| Fixed benchmark identity and quality gates | Every lane | Prevented false wins and false regressions | The Qwen35 graph-none `~15 tok/s` run looked like a regression until the missing `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'` identity field was caught. |
| One complete replica per GPU | Gemma 26B, Gemma 12B service | Avoided TP communication overhead; Gemma 12 c8 reached about `6.9x` c1 aggregate decode | Best when the model fits on one B70 and the workload is many independent requests or parallel experiments. |
| vLLM/XPU PIECEWISE graph with forced communicator capture/no-op | MiniMax, Qwen35 | Turned multi-GPU vLLM/XPU from fragile/slow into the `80-90+ tok/s` class | The exact graph flags are part of the result identity. |
| Model-specific fused kernels | MiniMax, Qwen27 Q4, Gemma26 | Qwen Q4 single-card `24.7` to best TP3 `50.1`; MiniMax AutoRound early `20` class to `80-90+` class over the full campaign | Generic env sweeps usually ran out of gains; source-level fusion and exact shape work mattered more. |
| Structured output with retry counted against throughput | MiniMax structured HTML | `89.563` effective tok/s with one reject to `94.406` with no rejects | Useful when the real task has a valid grammar. Do not present it as unconstrained generation. |
| Draft-MTP after the target baseline is stable | Gemma 26B | No-spec `74.297` to `124.977 tok/s` on the fixed cold suite | This only became useful after strict no-cache gates, target verification, and anti-history rules existed. |
| FlashAttention/VMM service tuning | Gemma 26B | Near-30K prompt prefill `702.6` to `947.6 tok/s`; broad UB2304 median `1076 tok/s` | Keep service/prefill recipes separate from short-decode LocalMaxxing records. |
| Prefix caching for repeated long prefixes | Gemma 12B service, MiniMax session-cache | Gemma 12 near-30K TTFT `22.44 s` to `3.75 s` on the repeated-prefix request | Valid service optimization, but not a fresh no-cache decode benchmark. |
| Preserving failed patches and negative results | All lanes | Saved repeated dead ends | Examples: MiniMax DFlash stalls, Qwen MTP invalid fast lanes, MiniMax IPC allreduce too slow, CCL direct regression. |

## What Usually Did Not Work

- Adding MTP/speculation early. It slowed validation and produced many invalid
  "fast" rows. Use it only after a no-spec baseline and gates are stable.
- Treating cache/history/repeated-continuation acceleration as fresh-response
  throughput. Gemma n-gram rows are useful diagnostics, not headline records.
- Comparing "same model" runs that changed graph mode, quantization,
  concurrency, context, prompt/output shape, or validation policy.
- Relying on broad environment roulette after the main path was understood.
  Useful gains tended to come from measured bottlenecks and source-level fixes.
- Promoting warm or stale AOT-cache artifacts without a fresh quality pass.

</details>

## Optimization Workflow

Use this order for a new model or hardware lane:

1. Define the metric first: generated-token decode, total tokens, prompt/prefill
   throughput, TTFT, aggregate concurrency, or service latency.
2. Create a quality gate before optimizing. Include exact-token or structured
   canaries, semantic checks, output hashes, and long-context checks when
   relevant.
3. Lock the benchmark identity in the run summary: model path/revision,
   quantization, engine, prompt/output shape, context, GPU layout, graph flags,
   memory utilization, fallback flags, and diagnostic flags.
4. Establish a boring no-spec baseline. Repeat it warm and cold enough to know
   normal variance.
5. Profile or trace one suspected bottleneck. Prefer a small A/B that answers
   one question over a large flag sweep.
6. Save every meaningful patch and result, including losses. Use `notes/`,
   `patches/`, `data/`, `results/`, `experiments/`, and `repro/` consistently.
7. Only after the target baseline is reproducible, try speculation, MTP,
   n-gram, prefix cache, or other acceptance/cache mechanisms.
8. Prove the result is not cached or cheating before submitting it: use unique
   prompts when required, record `cached_tokens=0`, count rejects, keep raw
   outputs, and rerun after restarting if cache state is suspicious.
9. Promote to a result packet or repro folder only when another person or agent
   can see the command, environment, quality status, throughput, and caveats.
10. Submit to LocalMaxxing only after the benchmark identity is real, the result
    beats the matching prior record, and the API key remains outside Git.

## Repository Map

- `repro/`: runnable promoted reproduction recipes.
- `results/`: promoted or closed result packets.
- `experiments/`: active research lanes that are not production recipes yet.
- `notes/`: chronological lab notes, including negative results.
- `patches/`: source/config deltas and failed-patch records.
- `data/`: compact run summaries, payloads, responses, and logs suitable for Git.
- `scripts/`: shared harnesses and submission helpers.
- `docs/`: human-facing maps and operating notes.

The repository does not include model weights, Hugging Face tokens, the
LocalMaxxing API key, full raw `/mnt/fast-ai/bench-results`, build outputs, or
Torch/AOT caches. Secret locations and sudo rules are documented in
[AGENTS.md](AGENTS.md), [docs/local-ops.md](docs/local-ops.md), and
[docs/localmaxxing.md](docs/localmaxxing.md).

## Hardware Scope

The active Intel lab has four Intel Arc Pro B70 32 GB cards, for `128 GB`
aggregate VRAM. That is enough for useful B70/Battlemage work across vLLM/XPU,
llama.cpp/SYCL, Level Zero, oneAPI, and LocalMaxxing-style records, but it is
also the main coverage limit. Larger high-VRAM Intel hardware would allow the
same workflow to move into GLM/DeepSeek-class models and longer active-context
lanes without turning every run into a capacity workaround.

Maintainer: Steve Seguin, with ongoing build notes at <https://x.com/xyster>.
