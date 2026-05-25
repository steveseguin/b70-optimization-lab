# 2026-05-25 C2 Quality Follow-Up And TurboQuant Probe

Goal: continue the CPU KV session-cache quality work, then test whether
TurboQuant can safely trade decode speed for a larger context window.

Production reminder: the stable endpoint remains the normal FP16-family KV
server at `32768` context. Everything here was temporary.

## Stable Production Lane

Restore command:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

Restored server after these experiments:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c1-restored-20260525T044056Z.log`

Smoke result:

- `/v1/models` reported `max_model_len=32768`.
- A short `/v1/completions` request returned successfully.

## Canary Script Updates

Updated:

`scripts/session_cache_canary.py`

New capabilities:

- `--prompt-mode fact-word`
- `--logprobs N` non-streaming request mode
- first visible logprob token capture when vLLM returns usable logprobs
- prompt version fields in the output JSON

Small logprob requests worked, but long-context logprobs hit a vLLM/XPU JSON
serialization failure:

```text
HTTP Error 400: Bad Request
Out of range float values are not JSON compliant: nan
```

Interpretation: logprobs are not usable as the long-context quality gate yet on
this stack. The likely issue is NaN logprobs escaping through the OpenAI API
response path at longer prompt sizes.

## C2 Quality Follow-Up

Temporary c2 server:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 16 \
  --max-num-seqs 2 \
  --no-scheduler-reserve-full-isl
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-32768-c2-kvoffload16-quality-20260525T040507Z.log`

Startup facts:

- `max_model_len=32768`
- `max_num_seqs=2`
- GPU KV cache size: `34304` tokens
- CPU KV offload budget: `4.0 GiB` per worker, about `16 GiB` total

### Strict-Word C2 Checks

Strict-word c2 checks passed at three prompt sizes:

| Prompt lines | Prompt tokens/session | Combined tokens | Result |
| ---: | ---: | ---: | --- |
| `264` | `7994` | `15988` | B/D expected word pass |
| `700` | `21074` | `42148` | B/D expected word pass |
| `1080` | `32474` | `64948` | B/D expected word pass |

Result files:

- `strict-word-c2-kvoffload16-quality-lines264-20260525T040717Z.json`
- `strict-word-c2-kvoffload16-quality-lines700-20260525T040729Z.json`
- `strict-word-c2-kvoffload16-quality-lines1080-20260525T040749Z.json`

The `700` and `1080` shapes exceed the `34304` GPU KV budget when both
sessions are combined, so these are real session-cache pressure tests.

### Fact-Word C2 Checks

Fact-word c2 checks also returned the expected words:

| Prompt lines | Prompt tokens/session | Result |
| ---: | ---: | --- |
| `264` | `6640` | B=`cobalt`, D=`amber` |
| `700` | `17540` | B=`cobalt`, D=`amber` |
| `1080` | `27040` | B=`cobalt`, D=`amber` |

Result files:

- `fact-word-c2-kvoffload16-quality-lines264-20260525T040809Z.json`
- `fact-word-c2-kvoffload16-quality-lines700-20260525T040819Z.json`
- `fact-word-c2-kvoffload16-quality-lines1080-20260525T040841Z.json`

Caveat: the GPU-only c1 fact-word baseline was brittle for B at the `700` line
shape, returning no visible first word. That makes fact-word useful as an
additional signal, but not yet a clean universal baseline.

### Sustained C2 Decode After Reload

Result file:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/checklist-c2-kvoffload16-sustained-lines1080-n128-20260525T040911Z.json`

Shape:

- prompt tokens/session: `24874`
- output target/session: `128`
- concurrency: `2`
- passes: `2`

Second pass after CPU KV reload:

| Label | Output tokens | Elapsed | TTFT | Decode after TTFT |
| --- | ---: | ---: | ---: | ---: |
| B | `128` | `2.426 s` | `0.477 s` | `65.68 tok/s` |
| D | `114` | `4.536 s` | `2.815 s` | `66.24 tok/s` |

Total wall output for the whole second pass was about:

```text
(128 + 114) / 4.536 s = 53.35 tok/s
```

Interpretation: after reload, per-request decode speed is still around
`66 tok/s` for this long-prompt c2 shape, but total wall throughput depends on
request skew and the slower request's TTFT.

## TurboQuant k8v4 Workspace Patch

Patch artifact:

`../../patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`

Local vLLM file patched:

`/home/steve/src/vllm/vllm/v1/attention/backends/turboquant_attn.py`

What changed:

- `_decode_attention`: if the shared workspace is locked, fall back to the
  attention function's internal buffer allocation path instead of crashing.
- `_continuation_prefill`: if the shared workspace is locked, allocate
  temporary K/V dequant buffers with `torch.empty`.

This is an experiment workaround, not a polished upstream patch. It trades
some allocation overhead for forward progress.

### Original Repro Failure

Command:

```bash
LOG_DIR=/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525 \
KV_DTYPE=turboquant_k8v4 \
PORT=18080 \
scripts/repro-minimax-turboquant-xpu-workspace-bug.sh
```

Original log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/server-turboquant_k8v4-ctx32768-20260525T041130Z.log`

Failure:

```text
Workspace is locked but allocation from 'turboquant_attn.py:851:_decode_attention'
requires 0.19 MB, current size is 0.00 MB.
```

### After Decode Fallback

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/server-turboquant_k8v4-ctx32768-20260525T041423Z.log`

Result:

- Server reached `/v1/models`.
- `GPU KV cache size: 80,128 tokens`.
- `Maximum concurrency for 32,768 tokens per request: 2.45x`.
- First simple completion returned HTTP 200.

Caveat: the simple prompt output looked poor, so this did not prove quality.

### After Continuation-Prefill Fallback

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/server-turboquant_k8v4-strict-prefillfix-20260525T042134Z.log`

Strict-word results:

| Prompt tokens | Label | Expected | Elapsed | TTFT | Decode after TTFT |
| ---: | --- | --- | ---: | ---: | ---: |
| `7994` | B | pass | `8.582 s` | `8.481 s` | `39.51 tok/s` |
| `7994` | D | pass | `5.636 s` | `5.557 s` | `50.26 tok/s` |
| `32474` | B | pass | `24.599 s` | `24.380 s` | `18.22 tok/s` |
| `32474` | D | pass | `24.263 s` | `24.043 s` | `18.15 tok/s` |

Result files:

- `strict-word-turboquant-k8v4-lines264-20260525T042322Z.json`
- `strict-word-turboquant-k8v4-lines1080-20260525T042345Z.json`

Sustained 24.9K prompt, 128-token decode:

| Label | Prompt tokens | Output tokens | TTFT | Decode after TTFT |
| --- | ---: | ---: | ---: | ---: |
| B | `24874` | `109` | `17.900 s` | `16.48 tok/s` |
| D | `24874` | `128` | `17.936 s` | `16.45 tok/s` |

Result file:

`checklist-turboquant-k8v4-lines1080-n128-20260525T042452Z.json`

Interpretation: TurboQuant k8v4 greatly improves KV capacity, but this
implementation is much slower than the normal FP16-family KV path on decode.

## TurboQuant Context Ceiling

### 64K Attempt

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/server-turboquant_k8v4-ctx65536-20260525T042617Z.log`

Result:

```text
ValueError: To serve at least one request with max seq len 65536,
1.64 GiB KV cache is needed, larger than available KV cache memory 1.52 GiB.
Based on the available memory, the estimated maximum model length is 60672.
```

Interpretation: `65536` is just over the practical limit with this graph/cache
shape.

### 60K Attempt

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525/server-turboquant_k8v4-ctx60000-20260525T043234Z.log`

Startup facts:

- `/v1/models` reported `max_model_len=60000`.
- `GPU KV cache size: 60,255 tokens`.
- `Maximum concurrency for 60,000 tokens per request: 1.00x`.

Near-ceiling strict-word result:

| Prompt tokens | Label | Expected | Elapsed | TTFT | Decode after TTFT |
| ---: | --- | --- | ---: | ---: | ---: |
| `58874` | B | pass | `61.624 s` | `54.040 s` | `0.53 tok/s` |
| `58874` | D | pass | `53.726 s` | `53.364 s` | `11.04 tok/s` |

Result file:

`strict-word-turboquant-k8v4-lines1960-ctx60000-20260525T043839Z.json`

Interpretation: 60K can start and can answer a constrained canary, but it is
not a good interactive endpoint yet.

## Current Recommendation

Keep the production endpoint on normal `32768` FP16-family KV.

The best practical experimental lane is still c2 CPU KV session caching:

- two near-32K sessions can be parked and reloaded
- first-word quality canaries passed against the GPU-only baseline
- second-pass reload TTFT was roughly `0.7-1.3 s` near max
- sustained post-reload decode was about `66 tok/s` per request after TTFT in
  the tested 24.9K prompt shape

TurboQuant k8v4 should remain a research lane:

- capacity improved from about `33792` FP16-family KV tokens to `80128`
  compressed KV tokens at a `32768` context server
- practical max server context was about `60000`
- strict canaries passed after the workspace fallbacks
- decode speed dropped sharply, to about `16.5 tok/s` at a 24.9K prompt and
  worse near 59K prompt tokens
- quality is not proven beyond narrow copy-word canaries
- Intel `ocloc` / IGC error 245 still appears during compile fallback

