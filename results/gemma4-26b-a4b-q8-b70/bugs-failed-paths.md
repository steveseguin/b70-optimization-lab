# Gemma 4 26B A4B Bugs And Failed Paths

This lane now has multiple validated local Gemma 4 26B Q8 results on one B70.
Keep this file focused on pitfalls, rejected mechanisms, and correctness risks
that should not be rediscovered.

Current promoted family:

- one complete Q8/INT8-quality model replica per B70, no TP split;
- llama.cpp SYCL / Level Zero;
- `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` target/verifier plus local
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` draft only;
- 1536-row chat canary before current record promotion;
- current filled-long record is tracked in
  [`research-plan.md`](research-plan.md) and
  [`localmaxxing-and-targets.md`](localmaxxing-and-targets.md).

## Known External Risks

- vLLM Gemma 4 MoE has a public issue for `--data-parallel-size > 1`; prefer
  four separate DP=1 servers for this lane.
- The 26B A4B MoE expert dimensions are reported by the vLLM Gemma 4 recipe as
  sensitive to 4-bit quantization. Treat W4A16 / INT4 AutoRound as a separate
  quality-risk lane, not the default.
- GGUF Q8 is large enough that KV headroom may be tight at 32K on a 32 GB B70.
  Establish small-context decode first, then walk context up.
- llama.cpp issue `#21893` reports B70/Gemma 4 nonsense output unless
  `GGML_SYCL_DISABLE_OPT=1` disables optimized SYCL reorder paths. This lane's
  launcher defaults to `=1`; any `=0` result needs repeat canaries before speed
  claims.
- Google's MTP guidance notes that MoE models at batch size 1 can see limited
  MTP speedup because different drafted tokens may activate different experts.
  Treat MTP as a follow-up after the no-spec baseline, not the starting point.
- `llama-server` built with IntelLLVM needs oneAPI runtime libraries in the
  loader path (`libsvml.so`, etc.). The launcher sources oneAPI automatically;
  raw `llama-server --help` from a fresh shell can fail until setvars is loaded.

## Local Carryover Risks

- Qwen experiments showed that fast speculative and graph paths often pass a
  small smoke but fail at repeat depth. Do not promote Gemma results without
  repeated canaries.
- llama.cpp multi-GPU syntax uses slash-separated devices such as
  `-dev SYCL0/SYCL1`; comma-separated syntax can mean separate benchmark cases.
  This lane should avoid multi-GPU splitting until the single-GPU replica path
  is understood.
- Old llama.cpp/B70 notes include Level Zero device loss, allocation failures,
  and graph/DNN toggles that can change performance sharply. Preserve exact env
  vars for every run.
- Partial downloads are a real risk for multi-GB GGUF files. The downloader is
  pinned to a commit and validates the primary Q8 byte size; do not replace it
  with an unpinned non-resumable command without recording revision and size.

## Local Rejected Or Risky Paths

- Deeper MTP budgets are not automatically better. On 2026-06-23, `n=8` with
  `p-min=0.08/0.10/0.12` and `n=9, p-min=0.12` all passed 384/384 canaries but
  fell to `61.8-65.9 tok/s` on the filled-long shape, far below the `n=7`
  record.
- The 2026-06-27 current-stack blind direct-unroll retest confirms the same
  failure mode. With the promoted route-cache / fused-output / selected-softmax
  / `UBATCH_SIZE=768` stack, `n=8`, `n=9`, `n=10`, and `n=12` all passed `64/64`
  canary rows with `cached_tokens=0`, but measured only `66.85`, `71.63`,
  `76.20`, and `82.93 tok/s` fresh row0 respectively. Do not run more blind
  `n>7` sweeps. Retest larger depth only after adding real direct-path
  confidence scores or reducing verifier MoE/LM-head cost. Note:
  `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0531-direct-unroll-depth-losses.md`.
- Draftless n-gram speculation can be target-verified and still be invalid as a
  fresh-response headline. On 2026-06-23, `ngram-mod match=20 min=32 max=64`
  reached `245-280 tok/s` only after repeated filled-long benchmark responses
  had populated continuation history. The cold first request stayed near
  non-spec speed (`~41 tok/s`). Those LocalMaxxing rows were submitted before
  the fresh/warmed rule was clarified and are marked retraction-needed; API
  deletion attempts returned 404 because LocalMaxxing exposes no documented
  benchmark delete/update endpoint. Future record attempts must report
  first-request fresh-response throughput separately and must not average
  warmed ngram repeats into headline throughput.
- llama.cpp `c926ad098` introduces server context checkpoints by default
  (`--ctx-checkpoints 32`). Default checkpoints preserved quality but inflated
  TTFT and hurt wall throughput for the benchmark lane. Use
  `--ctx-checkpoints 0` for record attempts unless the experiment is explicitly
  about checkpoint reuse.
- True draft KV `q8_0` tests require `FLASH_ATTN=on`; otherwise llama.cpp logs
  that V-cache quantization requires flash attention and the run is not a real
  q8 draft-cache benchmark.
- `--spec-draft-cpu-range-batch` is not supported by the pinned
  `dec5ca557` build and fails at launch. Use supported CPU mask/range flags
  only after confirming the target runtime exposes them.
- `LLAMA_GEMMA4_MOE_FUSED_ROUTER_SELECTED_WEIGHTS=1` is a valid loss on the
  current record stack. It fuses Gemma4 verifier router top-k plus selected
  softmax weight materialization into `GGML_OP_MOE_ROUTER_SELECTED_WEIGHTS`,
  and required a SYCL `F32 -> I32` copy/cast fix to avoid CPU fallback. The
  screen `data/gemma4-q8-gpu1-routerselectedweights-screen-20260627T050319Z/`
  passed `64/64` canary rows but reached only `101.52715106143687 tok/s`
  fresh row0 versus the current `104.22626983476746 tok/s` record. Patch:
  `../../patches/gemma4-26b-a4b-q8-b70/20260627T0503-llamacpp-gemma4-router-selected-weights-negative-current-stack.patch`;
  note:
  `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0503-router-selected-weights-negative.md`.
- `LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT=1` is a near-neutral
  screen, not a promoted win. It skips full gather/scatter for singleton expert
  routes in the current Q8 verifier gate/up `MUL_MAT_ID` shape while keeping the
  existing tuned matmul arithmetic. The candidate
  `data/gemma4-q8-gpu2-gateup-singleton-direct-screen-20260627T052517Z/`
  passed `64/64`, cached tokens were `[0]`, and the output hash matched the
  promoted record, but fresh row0 was `104.12278210887227 tok/s`, just under
  the `104.22626983476746 tok/s` record. Same-GPU flag-off control was slower
  (`102.16498485841758 tok/s`) but changed the benchmark hash. Keep this as a
  default-off artifact unless a node-profile comparison proves a real
  `ffn_moe_gate_up-*` reduction. Patch:
  `../../patches/gemma4-26b-a4b-q8-b70/20260627T0525-llamacpp-gemma4-gateup-singleton-direct-current-stack.patch`;
  note:
  `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0525-gateup-singleton-direct-screen.md`.
