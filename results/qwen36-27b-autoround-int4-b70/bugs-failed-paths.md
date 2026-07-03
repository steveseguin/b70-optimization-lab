# Qwen3.6 27B AutoRound Bugs And Failed Paths

This file starts empty by design. Add loader failures, wrong-output signatures,
bad flags, invalid fast paths, and negative optimizations here as they happen.

## Observed During Bring-Up

- Default thinking mode can return OpenAI `content=null` with generated text in
  the `reasoning` field. The first smoke hit this and exhausted `max_tokens=64`
  with `finish_reason=length`. The smoke and launch scripts now disable
  thinking by default via `chat_template_kwargs={"enable_thinking": false}` /
  `--default-chat-template-kwargs '{"enable_thinking": false}'`.
- Initial Intel checkpoint MTP2 smoke did **not** reproduce the public
  0%-acceptance MTP packaging failure. Metrics after manual probes plus smoke:
  `105` accepted draft tokens out of `108`.
- Bring-up used XPU graph off. Do not infer graph safety from the smoke.

## Watch List

- AutoRound loader mapping: ensure `quant_method=auto-round` and
  `packing_format=auto_round:auto_gptq` stay on an XPU-supported W4A16 path.
- `auto_round` Python package is not installed in the current vLLM venv; vLLM
  may not need it for inference, but any import-time dependency failure belongs
  here.
- MTP head packaging: plain AutoRound Qwen3.5/3.6 checkpoints may quantize
  `mtp.fc` into packed `fc.qweight`, while vLLM's MTP loader expects
  `fc.weight`. If MTP loads but gives 0% acceptance or no speedup, compare the
  Intel checkpoint against the Lorbus packaging before writing source code.
- Tokenizer config: related Qwen3.5 Intel AutoRound snapshots reportedly used
  an incompatible `TokenizersBackend` class. This Qwen3.6 snapshot currently
  reports `tokenizer_class=Qwen2Tokenizer`, so do not patch unless startup
  actually fails in tokenizer construction.
- The local vLLM CLI imports `/home/steve/src/vllm`; record source commit and
  any local diffs before interpreting performance.
- Built-in `qwen3_next_mtp` is useful but must be labeled and target-verified.
- Long context and four-replica service should not be attempted until short
  TP1 smoke is stable.
