# MiniMax Context And Speed Next Options

Date: 2026-05-23

Host state:

- Current deployable server: MiniMax M2.7 AutoRound INT4, vLLM/XPU TP4,
  OpenAI-compatible endpoint, `max_model_len=32768`.
- Current warm short OpenAI-compatible decode: `84.12` output tok/s after a
  near-full-context warm request.
- Current strict comparison lane remains p512/n1536 at `max_model_len=2048`.
- Current root-facing PCIe links are PCIe 4.0 x16. GPU endpoint sysfs entries
  still show the known internal `2.5 GT/s x1` bridge view.

## 93 tok/s vs 84 tok/s

Do not treat the 93 tok/s gap as proven PCIe bandwidth loss.

The earlier 93-class result was a warm speed path with more aggressive graph
capture/runtime behavior. Later notes put stricter caveats around that family:
it was fast and often semantically good, but did not clear the newer long exact
repeat/quality bar as cleanly as the conservative serving path.

PCIe 4.0 x16 is lower than PCIe 5.0 x16, but raw bandwidth does not line up as
the primary explanation. The MiniMax decode path has many small TP collectives,
so latency/topology can matter, but the per-token payloads are small compared
with PCIe 4.0 x16 bandwidth. Treat PCIe as a possible latency contributor, not
the main proven cause.

## Most Promising Context Options

### 1. FP8 KV cache

Priority: high.

vLLM now exposes:

```bash
--kv-cache-dtype fp8
--calculate-kv-scales
```

Upstream vLLM guidance currently presents FP8 KV cache as the best default KV
compression path: roughly 2x KV capacity with negligible accuracy loss in their
testing, and better behavior than the more aggressive TurboQuant presets for
most serving cases.

Local risks:

- XPU exposes FP8 support, but this must be tested on the B70 path.
- MiniMax AutoRound plus local XPU patches may hit backend-specific failures.
- Dynamic scale calculation may change output enough to require canary tests.

Safe test:

1. Stop the current server.
2. Start a temporary `VLLM_KV_CACHE_DTYPE=fp8` or direct
   `--kv-cache-dtype fp8` server at `32768`.
3. Check reported KV tokens and max concurrency.
4. Run raw exact canaries and semantic canaries.
5. Run p510/n1536 warm OpenAI decode and near-full-context smoke.
6. If clean, try higher context: `49152`, then `65536`.

Decision bar:

- Keep only if quality passes and warm decode does not regress materially.
- Promote only if 32K decode stays in the same band or the gained context is
  valuable enough to justify a clearly documented speed tradeoff.

### 2. TurboQuant KV cache

Priority: medium, experimental.

This build exposes:

```bash
--kv-cache-dtype turboquant_k8v4
--kv-cache-dtype turboquant_4bit_nc
--kv-cache-dtype turboquant_k3v4_nc
--kv-cache-dtype turboquant_3bit_nc
```

vLLM routes TurboQuant cache dtypes to a TurboQuant attention backend on XPU in
the local source tree, so this is no longer purely hypothetical.

Local risks:

- The vLLM study says FP8 remains the best default. TurboQuant `4bit_nc` is the
  practical memory-pressure option, but can trade off accuracy, latency, and
  throughput.
- More aggressive 3-bit modes are poor candidates for production because they
  can hurt reasoning and long-context quality.
- Backend presence does not prove B70 performance or correctness.

Safe test order:

1. `turboquant_k8v4` at 32K: lowest-risk capacity probe.
2. `turboquant_4bit_nc` at 32K: practical compression probe.
3. Only if both pass, try `49152` or `65536`.
4. Do not test `k3v4_nc` or `3bit_nc` for production unless the goal is purely
   exploratory.

Decision bar:

- Do not promote a TurboQuant mode unless it passes exact and semantic quality,
  has no NUL/control-token regressions, and either enables much more context or
  improves real long-context throughput.

## Most Promising Speed Options

### 3. Conservative graph-path recovery

Priority: high for speed, medium risk.

The 93-class path came from graph/runtime behavior, not from model or quality
cheating. The remaining work is to recover its speed while satisfying the newer
quality bar.

Safe path:

- Start from the current 84 tok/s server recipe.
- Reintroduce only one graph/runtime knob at a time.
- Require raw145 exact n64/n256, arithmetic repeat, semantic suite, and a
  longer generated-output repeat before accepting.

Do not publish or promote a new speed path that only passes short semantic
smokes.

### 4. N-gram speculation

Priority: low for MiniMax, useful for Qwen.

vLLM supports n-gram speculative decoding without a draft model. It can preserve
target-model quality because the target verifies proposed tokens.

Local history is negative for MiniMax:

- A random-token p512/n256 n-gram result fell to `12.267` output tok/s.
- A deeper n-gram attempt failed before generation because of KV pressure.
- Qwen FP8 benefited from n-gram speculation, so this is model/workload
  dependent.

For MiniMax, only retest with a highly repetitive real workload if needed. Do
not enable by default.

## Test Matrix

Keep each candidate isolated and reversible:

| Candidate | First context | First output test | Quality gate | Promote if |
| --- | ---: | --- | --- | --- |
| baseline | 32768 | p510/n1536 | already passed | current default |
| FP8 KV | 32768 | p510/n512 then n1536 | exact + semantic | same quality, no major speed loss |
| FP8 KV long | 49152/65536 | near-full + n64 | exact + semantic | more context without OOM |
| TQ k8v4 | 32768 | p510/n512 | exact + semantic | useful KV gain |
| TQ 4bit_nc | 32768 | p510/n512 | exact + semantic + long retrieval | much more context |
| n-gram | 32768 | repetitive prompt only | exact + semantic | clear win on target workload |
| graph recovery | 32768 or 2048 | p510/n1536 | strict long-repeat gate | 90+ tok/s and quality-clean |

## Suggested Immediate Next Step

Run a temporary FP8 KV server first. It is the best risk/reward candidate:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-cache-dtype fp8 \
  --calculate-kv-scales
```

If it starts and quality passes, test whether it can serve `49152` or `65536`.
If FP8 KV fails or regresses badly, try `turboquant_k8v4` only as an
experimental capacity probe.

## References

- vLLM n-gram speculation docs:
  https://docs.vllm.ai/en/v0.21.0/features/speculative_decoding/n_gram/
- vLLM TurboQuant study:
  https://vllm-project.github.io/2026/05/11/turboquant.html
- vLLM TurboQuant API docs:
  https://docs.vllm.ai/en/latest/api/vllm/model_executor/layers/quantization/turboquant/
- vLLM forum note on TurboQuant as KV-cache dtype, not model-weight
  quantization:
  https://discuss.vllm.ai/t/turboquant-kv-cache-compression/2503
