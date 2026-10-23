# Experimental text chat facade

[chat_service.py](chat_service.py) joins the [pinned codec](CHAT-CODEC.md) to an
already admitted [checkpoint engine](CHECKPOINT-ENGINE.md). It does not launch
an owner or open a socket. A coordinator supplies the model name, private
session ID, unique request ID, exact engine/tokenizer identity and independently
admitted native stop-token set.

For the p198 production owner, native geometry uses `eos=248044`, and the native
generation loop also stops at `248046`. The GGUF header names these
`<|endoftext|>` (BOS/padding) and `<|im_end|>` (GGUF EOS), respectively. The
coordinator passes `{248044, 248046}` from that native source/launch admission;
the codec must match it exactly. Tiny-host owners have different geometry and
stop semantics and cannot borrow this production admission.

The facade accepts text `system`, `developer`, `user` and `assistant` messages,
with a user message last, at most64 messages and65,536 content bytes. Thinking
is off. It permits one nonstreaming greedy completion: `temperature=0`,
`top_p=1`, `n=1`, `max_tokens=1..512`, within the admitted context. Unsupported
fields, tools, sampling and client stop strings refuse before owner intake.
The model must match exactly. An input refusal does not halt the owner.

The parking policy must use the exact bound codec callbacks. The service
serializes validation, generation, disposition and response assembly. It
preserves every generated ID in the checkpoint history, including a terminal
token. Only response text omits a final native stop token; whitespace is never
trimmed. Usage counts every generated token, and finish reason is `stop` for
a terminal token even at the cap, otherwise `length`. An early reply without
a terminal token, an internal stop token, malformed output or a runtime error
halts subsequent service intake. It neither retries nor replaces the owner.

[Synthetic boundary tests](test_chat_service.py) cover invalid input, callback
drift, stop-set admission, output preservation and halt behavior.
[Recorded-device replay](test_chat_service_replay.py) runs the actual pinned
codec and facade against the retained incident-retrospective and decision-memo
inputs and replies. The replay owner refuses any prompt differing from those
recorded token IDs; no native process or GPU work runs in that test. This is
response-assembly evidence, separate from native arithmetic and live serving.

This is a narrow experimental chat-completion shape. Streaming, tools,
concurrent decode, cancellation, authentication and full OpenAI compatibility
are not qualified. ctxkeeper's deployed HTTP request path remains unchanged.

## Joined real-model proof, 2026-10-23

[Packet199](../stage2/packet199-chat-parking/RESULT.md) subsequently passed six
actual HTTP turns through one unchanged device owner, this adapter stack and
bounded parking: 896 output tokens, five saves and one release. Resumed chat
matched fresh tokens and saved state; edited history selected fresh processing.
The independent audit verified HTTP mapping and usage and rehashed both surviving
checkpoints. Policy-deleted states retain captured digest evidence, with that
limitation explicit. All replies reached their caps. This is a bounded functional
pilot, without a general serving, natural-stop, cold-speed or throughput claim.
