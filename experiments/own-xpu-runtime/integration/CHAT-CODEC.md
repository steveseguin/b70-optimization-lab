# Pinned text chat codec

## Question and identity

Can a text facade render and tokenize messages using the exact vocabulary and
chat template behind the native checkpoint identity?
[chat_codec.py](chat_codec.py) admits only GGUF header `7c1460a9…`, oracle
source `1c284c06…`, template `12827f24…`, and native tokenizer TSV `5e88b69b…`.
The constructor reads exactly 10,946,618 header bytes, verifies them before
parsing, and reconstructs the native vocabulary byte stream in memory to verify
`vocab_bin_sha256=7a0e6124…`. It never reads model tensor payloads.

## Outcome

`PinnedChatCodec(*, gguf_path=DEFAULT_GGUF)` exposes `render(messages)`,
`encode(text)`, `decode(token_ids)`, `vocab`, `terminal_token_ids`, and
`tokenizer_identity`. The identity is the exact native five-key mapping;
terminal role information and Python dependency versions are separate.

The existing `/home/steve/.venvs/vllm-xpu/bin/python` provides regex 2026.5.9 and
Jinja2 3.1.6. System Python lacks regex. There is no dependency installation,
Hugging Face tokenizer fallback, model execution, or automatic native launch.

## What worked

Seven CPU tests verify all 12 sealed prompt texts and complete token lists,
four retained multi-message shape hashes, Unicode and whitespace preservation,
identity equality, malformed-input refusal, and changed header/source/vocabulary
pin refusal. The exact template renders with `add_generation_prompt=True` and
`enable_thinking=False` in Jinja2's immutable sandbox.

The accepted input is 1–64 messages, each containing only `role` and string
`content`; roles are system, developer, user or assistant. Content totals and
rendered text are limited to 65,536 UTF-8 bytes. Encode and decode are bounded to
32,768 token IDs. A smaller engine context limit remains the facade's concern.

## What failed or remains uncertain

The GGUF EOS is 248046 (`<|im_end|>`). Token 248044 (`<|endoftext|>`) is GGUF
BOS/padding and the native geometry's separate primary stop ID. Both are
verified control tokens and exposed as terminal IDs; this does not conflate
their header roles. The facade must independently admit its native stop set.

Decode removes nothing, including terminal strings or whitespace. A facade may
remove a final terminal ID from displayed content while retaining the complete
raw generated IDs for checkpoint history. Incomplete UTF-8 token pieces follow
the pinned oracle's replacement-character behavior. This codec qualification
covers text conversion, not a live serving endpoint or new model quality claim.

## Evidence and patches

The implementation and tests are additive; parity and sealed packet files are
unchanged. See [tests](test_chat_codec.py),
[receipt](receipts/chat-codec-cpu-20261023.json),
[test log](receipts/chat-codec-cpu-20261023.log), and the original
[template](chat_template-7c1460a9.jinja).

```bash
nice -n19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration -p test_chat_codec.py -v
```

## When to revisit

A different model revision, tokenizer source, native identity TSV, template,
terminal policy, or Python rendering/tokenizer dependency requires explicit
readmission and exact parity checks. Tool calls, multimodal content and thinking
mode are outside this text-only interface.
