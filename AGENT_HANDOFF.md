# Codex Agent Handoff

Last updated: 2026-05-23

This file is the first thing a new Codex agent should read when continuing the
Intel Arc Pro B70 LLM optimization work.

## Current Objective

Primary target:

- MiniMax M2.7 INT4 AutoRound on 4x Intel Arc Pro B70 32GB.
- Preserve answer quality while improving single-session decode, context,
  prefill, and eventually concurrent-session throughput.
- Do not use power-limit or overclocking changes as optimization paths.

Secondary targets:

- Qwen3.6 27B Q4_0 GGUF and FP8 on B70.
- MiniMax M2.7 GGUF remains useful as a capacity/quality comparison but is not
  the current speed path.

## Current Promoted MiniMax State

Current validated structured-output fast lane:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: local vLLM/XPU `0.20.1-local`, TP4
- Backend stack: Level Zero/XPU, llm-scaler INT4 MoE kernels, forced XPU graph
  with communicator capture no-op
- Task: constrained simple HTML, `skeleton_status_html`
- Result: `94.406 tok/s` effective accepted output, `94.692 tok/s` post-first
- Quality gate: `30/30` accepted, `0` rejects, `100%` first-attempt pass
- LocalMaxxing: `cmphg048s00mppc0192sahyug`
- Note: `notes/2026-05-22-minimax-structured-fast-lane-regex2.md`
- Payload: `data/localmaxxing-minimax-m27-autoround-structured-regex2-20260522.payload.json`

Important caveat:

- This is a constrained structured-output lane. It does not prove unconstrained
  free-form website generation is clean on the forced XPU graph path.
- Structured JSON cross-check passed `9/9` with `0` rejects at `87.956 tok/s`
  and stable parsed JSON hashes.

Current older strict long-run MiniMax baseline:

- p512/n1536, ctx2048, batch 1
- Result: `89.314195 tok/s` output, `119.085594 tok/s` total
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`
- Repro folder: `repro/minimax-m27-b70-89tps-20260520/`

Current fresh Ubuntu 24 deployment repro:

- Date: 2026-05-23
- Purpose: reproduce the deployable OpenAI-compatible vLLM endpoint on a mostly
  fresh Ubuntu 24.04 host with 4x B70s.
- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Endpoint: vLLM OpenAI-compatible server on `0.0.0.0:8000`
- Served context default: `24576` via `/home/steve/bin/minimax-vllm-serve` and
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/06-serve-openai-compatible.sh`
- Context used for the comparable smoke/quality lane: `2048`
- Quality gate: passed raw token-hash canaries, semantic suite, arithmetic
  repeat, and extended sixpack.
- Benchmark: `110.896 total tok/s`, `83.172 output tok/s` for p512/n1536.
- OpenAI endpoint context validation: `24576` started with
  `gpu_memory_utilization=0.95`, vLLM reported `25,344` GPU KV-cache tokens,
  prompt 24,400 / output 64 completed without OOM, and short decode remained
  `83.78-83.79 output tok/s` before/after the long-context request.
- Failed context checks: `32768` and `25600` failed vLLM KV-cache memory checks;
  vLLM estimated the practical ceiling around `25,344` tokens.
- Repro folder:
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/`
- Human deployment guide: `docs/b70-minimax-ubuntu24-deployment.md`
- Docs index: `docs/README.md`
- Model/community recipe index: `docs/model-recipes.md`
- Community results/build notes: `docs/community-results.md`
- Intel feedback: `docs/intel-b70-minimax-feedback-20260523.md`
- Lessons learned:
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/notes/learnings-20260523.md`

This fresh deployment is not the fastest output-token lane known in the repo.
Treat it as the current best documented "install from a fresh system and serve
on the LAN" baseline.

## Quality Rules

Do not promote a speed result unless quality is preserved.

For low-level MiniMax performance changes, use the strict gates already in the
repo:

- raw145 exact token hashes at n64 and n256
- semantic canaries
- arithmetic repeat
- extended sixpack

For practical task lanes:

- validate generated output structurally, not just token speed
- count rejected attempts against effective throughput
- keep raw outputs and result JSON under `/home/steve/bench-results/...`
- label constrained-output results as constrained; do not present them as
  unconstrained general generation quality

## Key Repro Paths

Start here on a fresh machine:

- `docs/b70-minimax-ubuntu24-deployment.md`
- `repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`
- `repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/`
- `repro/minimax-m27-b70-89tps-20260520/README.md`
- `repro/minimax-m27-b70-89tps-20260520/scripts/00-install-system-deps.sh`
- `repro/minimax-m27-b70-89tps-20260520/scripts/01-download-model.sh`
- `repro/minimax-m27-b70-89tps-20260520/scripts/02-build-stack.sh`
- `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`
- `repro/minimax-m27-b70-89tps-20260520/patches/`

Important notes:

- The 2026-05-23 repro is the best starting point for building a working
  endpoint from a fresh Ubuntu 24 system. It includes low-RAM SSD swap handling,
  a LAN bind server script, and Intel-facing failure notes.
- The repro folder is for the `89 tok/s` strict baseline, not the latest
  `94 tok/s` constrained HTML lane.
- The latest structured regex2 fix is recorded as a patch in
  `patches/minimax-website-structured-regex2-20260522.patch`.
- For the latest `94 tok/s` structured regex2 lane, use the focused public
  runner at `scripts/run-minimax-structured-skeleton-quality.py`. The broader
  local lab harness has more exploratory options, but this runner is the
  public reproducible harness for the promoted constrained HTML lane.

## Known Good Runtime Shape

Typical promoted environment flags include:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset VLLM_XPU_CUDAGRAPH_PARTITION_COLLECTIVES || true
unset VLLM_XPU_CUDAGRAPH_STATIC_INPUT_COPY || true
```

For the structured HTML fast lane:

```bash
python scripts/run-minimax-structured-skeleton-quality.py \
  --mode graph \
  --warmup-runs 1 \
  --repeat 30 \
  --retry-until-pass 5 \
  --max-tokens 96 \
  --max-model-len 4096 \
  --max-num-batched-tokens 512
```

Expected regex2 result class:

- `30/30` accepted
- `0` rejected attempts
- output throughput around `94 tok/s` after warmup on matching hardware

## What Is Not Fully Solved

- Unconstrained free-form website output on the forced XPU graph path can still
  corrupt or degrade. Keep validating practical tasks.
- JSON structured lanes are better than free-form but can run below the HTML
  fast lane; use parsed JSON validation and count retries.
- Concurrency 2 is not ready. Prior c2 graph/no-graph attempts hit stalls or
  Torch XPU indexing assertions.
- Larger prefill chunks such as 1024 tokens can trigger Intel `ocloc`/IGC
  compiler failures on this stack; keep `max_num_batched_tokens=512` unless
  testing that specifically.
- Generic in-place allreduce thresholds were usually slower. Favor exact
  shape/dtype fusion with quality proof.

## Optimization Directions

Best next work:

- Expand validated practical tasks while keeping the 90+ tok/s lane.
- Build reliable prefill/context measurements without lowering decode quality.
- Debug c2/concurrency failures with small two-request repros.
- Continue lower-level fusion only where math is exactly preserved:
  Q/K variance allreduce plus RMS apply, hidden allreduce plus residual/RMSNorm,
  MoE output plus epilogue, and final projection/lm-head boundaries.
- Mine llm-scaler for ideas, but require strict quality gates before promotion.

Avoid:

- claiming constrained decode as unconstrained quality
- comparing AutoRound INT4 as equivalent to Q4_0/FP8 without separate quality
  checks
- disabling clones/allreduces broadly without exact shape and quality proof
- power tuning as the explanation for speed

## GitHub And LocalMaxxing

Use the GitHub connector path for publishing, not local shell auth.

Significant benchmark results should be submitted to LocalMaxxing with payloads
and responses recorded under `data/`.

Recent important LocalMaxxing IDs:

- MiniMax structured regex2: `cmphg048s00mppc0192sahyug`
- MiniMax strict p512/n1536 high: `cmpct6t4m007fnw01yjdtlcs4`
- JSON gated c1 practical task: `cmpgv9p9j007qpc01oq5zqhdg`
- JSON c1 2k-context follow-up: `cmpgx0yrb009fpc0183xjri4j`

## Models Expected On Disk

Main models of interest:

- `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Qwen3.6 27B Q4_0 GGUF
- Qwen3.6 27B FP8
- MiniMax M2.7 GGUF/UD-IQ4_XS for comparison

The model weights themselves are not in GitHub. Use the repro download scripts
and local Hugging Face cache conventions from the repro folder.
