# Qwen3.6 Q4_K_M F16-KV TP1 MTP1 parent sentinel preregistration

This packet asks one narrow question before spending a seven-depth campaign:
does embedded one-token MTP boot, engage, preserve target output, and pass the
quality battery at an exact 8K active context on one B70?

It does **not** use `llama-bench` as evidence for speculation. `llama-bench`
does not exercise the serving speculative loop. The packet instead boots the
checksum-pinned `llama-server` twice and uses target-verified HTTP generation:

1. MTP0 control: one 8,192-token exact-ID prompt and 128 streamed output IDs.
2. MTP1 candidate: the identical request with embedded `draft-mtp`, `n_max=1`,
   `n_min=1`, and `p_min=0`, followed by the bounded Qwen3.6 quality suite.

The exact-depth client requires `usage.prompt_tokens=8192`, zero cached tokens,
no truncation or context shift, 128 returned IDs, and the conventional 99
interval timing window. Candidate and control output-token hashes must match.
The candidate server log must also report nonzero generated and accepted draft
tokens. Those counters arise after target verification in llama.cpp's serving
loop; the same checksum-pinned GGUF supplies both target weights and its
embedded MTP tensors, and an external draft path is forbidden.

The quality arm requires the exact-answer, copy, arithmetic, and JSON canaries;
two identical greedy repeats; the 8K needle; and `cached_tokens=0` for every
request. This is a parent sentinel, not a promoted matrix row. Its synthetic
8K serving rate is labeled HTTP serving evidence and must not be mixed with
raw `llama-bench` rates or featured realistic-suite speeds.

There is no speed floor. If every identity, exact-depth, target-parity,
draft-engagement, quality, cache, and cleanup gate passes, expand MTP1 into a
separately preregistered seven-depth curve even if this sentinel is slower than
MTP0. Otherwise preserve the failure and do not expand from this packet.

Run only from clean pushed `main`, with GPU0 idle and no model/container work:

```bash
bash experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.sh \
  --ack 'RUN qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r1'
```

The runner acquires all four canonical locks, rejects llama benchmarks and
servers plus bare or containerized vLLM work, repeats the idle census directly
before each arm, creates the frozen ext4 run root exactly once, tears each
server down before the next arm, writes a terminal receipt, and never edits the
family catalog or site.
