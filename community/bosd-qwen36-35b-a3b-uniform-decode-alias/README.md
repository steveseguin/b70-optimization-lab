# Uniform-decode shape-alias (vllm #53051) — on-demand repro on Qwen3.6-35B-A3B + fix confirm

This packet corroborates [`community/dominick253-qwen38-27b-fp8-uniform-decode-alias/`](../dominick253-qwen38-27b-fp8-uniform-decode-alias/)
(PR #45) from a **second, independent Arc Pro B70 host**, and turns its
"degenerate walls after 6–24 h dwell" into a **deterministic on-demand
reproduction that takes seconds** — then confirms the upstream fix clears it.

## Why this lane cares

`GPUModelRunner._is_uniform_decode` classifies a batch as uniform decode by
**shape only**:

```
max_num_scheduled_tokens == uniform_decode_query_len
    and num_tokens == max_num_scheduled_tokens * num_reqs
```

With speculative decoding, `uniform_decode_query_len = 1 + num_spec_tokens`. So
any **prefill** step that schedules exactly that many tokens per request — a
tiny prompt, a chunk tail, a prefix-cache-hit tail, a mixed batch — *aliases*
the uniform-decode shape. Dispatched into a cudagraph captured for uniform
decode, it replays capture-time metadata with null/stale **GDN** recurrent-state
indices, silently skips the state write, and the zeroed state produces
degenerate single-token logits (`!!!!!`, `0000`, `oooo`).

**Qwen3.6-35B-A3B is a GDN model.** Its `config.json` `layer_types` interleaves
`linear_attention` (gated delta net) with `full_attention` every 4th layer
(`full_attention_interval: 4`). Served under vLLM-XPU with MTP2
(`num_speculative_tokens=2` → `uniform_decode_query_len=3`), it runs the buggy
classifier and is exposed to exactly this defect. The lane's existing
`patch_mtp_boundary.py` guards a *different* GDN+spec edge (a partial final
speculative group at the max-len boundary), not this prompt-length alias.

## The on-demand trigger (the novel bit)

The original packet noted it had **no controlled on-demand reproduction** — the
incident needed real mixed-traffic dwell. This host gets it in one request:

On an otherwise idle server, a **fresh request whose prompt tokenizes to exactly
`1 + num_spec_tokens` tokens** has, on its prefill step (`num_reqs=1`):

- `max_num_scheduled_tokens == 1+num_spec_tokens == uniform_decode_query_len`, and
- `num_tokens == (1+num_spec_tokens) * 1`,

so stock `_is_uniform_decode` returns `True` for a **prefill** → misdispatch →
zeroed GDN state → garbage first token. Neighboring prompt lengths do not alias
and stay clean. At MTP2 the alias length is **3 tokens**.

`reported/alias-harness.py` measures the effect: it picks real K-token prompts
via the server's `/tokenize`, fires 30 greedy (`temperature=0`) completions per
shape, and flags degenerate single-token walls.

## Result (this host)

30 greedy repeats per shape, `qwen36-35b-moe`, MTP2:

| prompt shape | tokens | **stock** | **patched (#53059)** |
| --- | --- | --- | --- |
| **alias** (`1+1`, = 1+spec) | 3 | **18/30 = 60%** `!!!!!` walls | **0/30** |
| short (`Hi`) | 1 | 10/30 = 33% | **0/30** |
| control (`Hi.`) | 2 | 0/30 | 0/30 |
| control (long) | 13 | 0/30 | 0/30 |

Corruption is isolated to `prompt_len == uniform_decode_query_len`. Post-fix,
arithmetic is correct (`17*23=391`) and the server's own SpecDecoding metrics
still report mean acceptance length **2.25–2.31** (~65% draft acceptance) — the
guard rejects only aliased prefills; genuine decodes keep the MTP fast path.

Full tables and raw run JSON: [`reported/repro-results.md`](reported/repro-results.md).

## The fix

Upstream [vllm #53059](https://github.com/vllm-project/vllm/pull/53059)
(`allenzz-dev`): after the shape test passes, additionally require every request
to be **past its prompt**
(`input_batch.num_computed_tokens_cpu[:n] >= input_batch.num_prompt_tokens[:n]`).
`_is_uniform_decode` becomes an instance method; the sole call site already uses
`self.`, so no call-site change is needed.

`reported/patch_uniform_decode_alias.py` applies exactly that guard as an
entry-time monkeypatch, in the same idiom as this lane's existing
`patch_mtp_*.py` (locate via importlib, MARKER-idempotent, fail-loud). It is an
alternative *deployment shape* to the R50 bind-mount; the classifier change is
identical to #53059.

## Reproduce

```bash
# against any vLLM-XPU server running a GDN model with spec decode:
python3 reported/alias-harness.py \
  --base http://localhost:8000/v1 --model <served-name> \
  --spec-tokens <num_speculative_tokens> --iters 30 --tag stock
# apply patch_uniform_decode_alias.py at container entry, restart, then:
python3 reported/alias-harness.py ... --tag patched
```

Stock shows a nonzero rate at the `1+spec`-token shape and zero elsewhere;
patched shows zero everywhere. PR #45's `test_is_uniform_decode_red_green.py`
(stdlib + numpy) also passes RED/GREEN here.

## Attribution

Root cause and lane: `dominick253` (PR #45). Fix: upstream vllm #53059
(`allenzz-dev`), issue #53051. This packet: independent B70-host on-demand
reproduction + fix confirmation by `bosd`. `community-reported` — not a
reference-lab run.
