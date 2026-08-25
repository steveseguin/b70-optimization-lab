# Qwen3.8 Q8_0 weights / F16 KV TP1 local r2 result

Status: **complete raw-engine depth evidence; model quality and HTTP serving
remain separate gates.**

The exact one-B70 invocation completed all fourteen preregistered rows with
five samples each. Q8_0 weights plus F16 KV fit through the full 32K active
context point; no allocation fallback, KV substitution, depth deletion, MTP,
or graph mode was used.

| existing context depth | pp2048 tok/s | tg128 tok/s |
| ---: | ---: | ---: |
| 0 | 996.891020 | 19.662501 |
| 2K | 987.388875 | 19.592508 |
| 4K | 959.560446 | 19.509481 |
| 8K | 914.062353 | 19.293993 |
| 16K | 837.512717 | 18.838870 |
| 24K | 773.146408 | 18.418098 |
| 32K | 719.144647 | 18.023689 |

Decode falls only 8.3% from the directly measured zero-depth point to 32K;
prefill falls 27.9%. The values are raw `llama-bench` rates, not the package's
realistic-suite metric and not a service-user curve. The older Q4_K_M depth
sweep used another frozen binary, so its numerically higher Q4 decode and
lower Q4 prefill are descriptive cross-profile observations—not a matched
quantization A/B or a quality conclusion.

Evidence:

- [validated result with all samples](../data/qwen38-q8weights-f16-tp1-local-20260825-r2/result.json)
- [unmodified llama-bench JSON](../data/qwen38-q8weights-f16-tp1-local-20260825-r2/raw.json)
- [command](../data/qwen38-q8weights-f16-tp1-local-20260825-r2/command.txt),
  [environment](../data/qwen38-q8weights-f16-tp1-local-20260825-r2/environment.txt),
  and [input hashes](../data/qwen38-q8weights-f16-tp1-local-20260825-r2/sha256sums.txt)
- [preregistered contract](../data/2026-08-25-qwen38-q8weights-f16-tp1-local-r2-prereg.json)

Next publication gate: run a cache-zero semantic/repeat battery with this exact
model/runtime profile, then create a separate one-card Q8 package. Do not add
these points to the existing two-card Q8 package or imply TP2 behavior.
