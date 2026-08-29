# Qwen3.8 AutoRound current-runtime deterministic MTP0 preregistration

Date: 2026-08-28
Status: amended before execution; composite image build pending

## Question

Do the deterministic GDN B/A padding, compiler-visible recurrent-state
contract, explicit oneCCL `Work.wait()`, and deterministic Inductor treatment
make the current `ac7509e2b` TP2 AutoRound INT4 target repeat exactly without
changing its eager target output?

This is a correctness recovery campaign. It is not an MTP arm, record attempt,
or permission to promote a speed. The historical 101.170 tok/s MTP5 research
anchor remains quarantined.

## Frozen identity

- measuring host `steve-b70s`, physical GPUs 2 and 3, TP2;
- local-NVMe real directory
  `/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-devan`, copied from the
  retained USB source and verified after copying through all 19 direct and
  ordinary manifest identities;
- model revision `bce40cacab0a4535b92fb3d57615c2bea9adf3d1`;
- vLLM `ac7509e2b`, base image
  `f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`;
- composite deterministic image tag
  `neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1`;
- base image
  `neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31`, remote
  manifest ID `2f153c9e603f1dd28120b31fc1980edfaf01853d3db1b55c444c387d0631aa15`;
- the remote manifest ID differs from the locally validated ID because the
  remote builder emitted attestations, but all five installed patched file
  SHA-256 identities match the validated local image exactly;
- XPU-kernels source `1e90ffa672ba02f17a909da11838a4c55b199783`
  plus the repository oneDNN W4A16 determinism pad. This was added to the
  frozen treatment before execution after preflight proved that the FP8 base
  did not contain the required INT4 binary marker; the composite image ID,
  `_xpu_C.abi3.so` SHA-256, and paired GDN-library SHA-256 will be frozen here
  after the clean build and before the first attempt;
- AutoRound/INC W4A16, FP16 activations and KV, MTP0, XPU Graph off,
  compiler `cudagraph_mode=NONE`, deterministic Inductor on, prefix caching
  off, seed 42, one sequence;
- explicit oneCCL P2P and completion wait, persistent GDN scratch on;
- complete fixed 12-prompt/six-class suite SHA-256
  `df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac`,
  natural 512 cap, each prompt exactly once, token IDs returned, cache zero.

## Ordered campaign

1. One fresh eager MTP0 oracle, new cache and evidence roots.
2. Only if it passes every workload and canary gate, one fresh compiled MTP0 A.
3. Only if A passes, one fresh compiled MTP0 B with another empty cache.
4. Compare complete token arrays. Promotion authority requires compiled A/B
   12/12 equality and each compiled arm 12/12 equality to the eager oracle.

Each arm independently re-verifies all model files through direct and ordinary
reads, requires quantization `inc`, the frozen image and treatment variables,
both TP workers, no XPU Graph capture, all 12 strict rows, median-of-class-
medians over the 99 intervals between events 1--100, zero cache tokens, the
independent canary battery, bounded cleanup, and no new GPU2/3 reset/fatal
event. A selected fixture, warm prompt, early-EOS metric refusal, or one good
compiled arm cannot pass.

If any arm or comparison fails, stop and preserve it. No retry is authorized
under this preregistration. A complete pass establishes only a deterministic
MTP0 parent and authorizes a separately preregistered MTP1 candidate; it does
not validate MTP1--5, graphs, long context, concurrency, or a public speed.

Executables:

- `../../../repro/qwen38-27b-autoround-int4-b70/scripts/run-current-deterministic-mtp0-server.sh`
- `../scripts/run-20260828-qwen38-autoround-deterministic-mtp0-strict-attempt.sh`

## Pre-execution build qualification

No model request has run under this preregistration. Two preserved local build
roots failed closed before image creation: the first exposed Bash nounset in
Intel's `setvars.sh`; the second compiled successfully but the wrapper then
caught that it had extracted `_C.abi3.so`, while oneDNN W4A16 is registered in
`_xpu_C.abi3.so`. The corrected builder compiles the lane's XPU-specific and
GDN targets, overlays the paired `_xpu_C.abi3.so` and
`libgdn_attn_kernels_xe_2.so`, and requires the marker and both operator
registrations before it can create the image. Those build-only failures are
not benchmark attempts or performance evidence.
