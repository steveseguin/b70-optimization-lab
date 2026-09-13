# Reproduction results — Qwen3.6-35B-A3B, MTP2, single B70

Host: independent 2× Arc Pro B70 (one card, `ZE_AFFINITY_MASK=2`), Fedora 44,
kernel 7.1.8, vLLM `0.26.1rc1.dev457+gc810e5ee9` (`vllm-openai-xpu@2c427ef`),
model served as `qwen36-35b-moe`, `--speculative-config {"method":"mtp","num_speculative_tokens":2}`.
Harness: `alias-harness.py`, 30 greedy (`temperature=0, seed=12345`) repeats per shape.
Degenerate = `(.)\1{7,}` run or ≥70% dominant non-alphanumeric char.

## Stock (unpatched `_is_uniform_decode`)

```
ALIAS k=3 (=1+spec)   prompt='1+1'   degenerate=18/30 rate=0.60   e.g. repeat:'!'x24
control k=1           prompt='Hi'    degenerate=10/30 rate=0.333  e.g. repeat:'!'x24
control k=2           prompt='Hi.'   degenerate= 0/30 rate=0.0
control long (13tok)  prompt=<13tok> degenerate= 0/30 rate=0.0
```

raw:

```json
{"base": "http://localhost:8000/v1", "model": "qwen36-35b-moe", "spec_tokens": 2, "tag": "stock", "ts": "2026-09-09T12:35:35", "results": [{"label": "ALIAS k=3 (=1+spec)", "prompt": "'1+1'", "iters": 30, "degenerate": 18, "rate": 0.6, "samples": [["repeat:'!'x24", "!!!!!!!!!!!!!!!!!!!!!!!!"], ["repeat:'!'x24", "!!!!!!!!!!!!!!!!!!!!!!!!"], ["repeat:'!'x24", "!!!!!!!!!!!!!!!!!!!!!!!!"]]}, {"label": "control k=1", "prompt": "'Hi'", "iters": 30, "degenerate": 10, "rate": 0.333, "samples": [["repeat:'!'x24", "!!!!!!!!!!!!!!!!!!!!!!!!"], ["repeat:'!'x24", "!!!!!!!!!!!!!!!!!!!!!!!!"], ["repeat:'!'x24", "!!!!!!!!!!!!!!!!!!!!!!!!"]]}, {"label": "control k=2", "prompt": "'Hi.'", "iters": 30, "degenerate": 0, "rate": 0.0, "samples": []}, {"label": "control long (13tok)", "prompt": "'The quick brown fox jumps over the lazy dog and then keeps running'", "iters": 30, "degenerate": 0, "rate": 0.0, "samples": []}]}
```

## Patched (upstream #53059 guard applied at entry)

```
ALIAS k=3 (=1+spec)   prompt='1+1'   degenerate= 0/30 rate=0.0
control k=1           prompt='Hi'    degenerate= 0/30 rate=0.0
control k=2           prompt='Hi.'   degenerate= 0/30 rate=0.0
control long (13tok)  prompt=<13tok> degenerate= 0/30 rate=0.0
```

raw:

```json
{"base": "http://localhost:8000/v1", "model": "qwen36-35b-moe", "spec_tokens": 2, "tag": "patched", "ts": "2026-09-09T12:40:08", "results": [{"label": "ALIAS k=3 (=1+spec)", "prompt": "'1+1'", "iters": 30, "degenerate": 0, "rate": 0.0, "samples": []}, {"label": "control k=1", "prompt": "'Hi'", "iters": 30, "degenerate": 0, "rate": 0.0, "samples": []}, {"label": "control k=2", "prompt": "'Hi.'", "iters": 30, "degenerate": 0, "rate": 0.0, "samples": []}, {"label": "control long (13tok)", "prompt": "'The quick brown fox jumps over the lazy dog and then keeps running'", "iters": 30, "degenerate": 0, "rate": 0.0, "samples": []}]}
```

## Post-fix functional / regression checks

- `17*23=` → `391` (correct)
- 3-token `1+1` → coherent tokens (was `!!!!!`)
- Server SpecDecoding metrics (journal): mean acceptance length **2.25–2.31**,
  ~65% draft acceptance — MTP spec-decode still active; the guard rejects only
  aliased prefills.

## CPU classifier test

PR #45's `test_is_uniform_decode_red_green.py` (stdlib + numpy) run here:
**RED PASS / GREEN PASS** (stock misclassifies all 5 aliased shapes; patched
rejects them and preserves all genuine decodes).
