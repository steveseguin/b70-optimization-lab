# Qwen3.6 Streaming-Input Verifier Probe

This probe starts an internal vLLM streaming-input session and feeds accepted baseline tokens back one at a time.

- baseline JSON: `data/qwen36-quark-int8-tp4-accepted-current-apiids-p512o128-20260611h.json`
- model: `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- tensor parallel size: `4`
- max model len: `32768`
- prefix caching: `False`
- seed: `20260611`
- generated-token logprobs: `20`
- max tokens per case: `27`
- preflight only: `False`
- all matched: `False`

| Case | Checked | Matched | First mismatch | Session tok/s |
| --- | ---: | ---: | --- | ---: |
| `natural_latency_plan` | 26 | 25 | pos 25 expected `198` got `271` | 1.75 |

Interpretation:

- If this aligns while re-prefill drifted, a resident-KV sidecar remains a credible verifier design.
- If this drifts too, move directly to in-engine copy-on-write request/KV forking.
- Throughput here includes harness overhead and should not be used as a production speed claim.
