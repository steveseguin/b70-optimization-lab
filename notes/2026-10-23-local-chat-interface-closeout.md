# Local chat interface: CPU integration closeout

## Question and identity

Can the admitted warm owner be reached through a text chat interface while
keeping its exact tokenizer, checkpoint policy and stop semantics? This step
adds a pinned codec, serialized chat facade and loopback HTTP adapter around
the existing p198 protocol. It changes no native arithmetic or sealed source.

## Outcome

All38 chat CPU tests pass. The codec reproduces12 sealed prompts exactly and
four recorded message shapes. The joined socket test sends real messages
through HTTP, the chat facade and the pinned codec, then replays the retained
87→256 and60→128 token device cases. Responses, usage and raw token histories
match. This test starts no native model process.

## What worked

Unsupported input refuses before generation. The native stop set is admitted
independently of the codec, and final stop tokens stay in checkpoint history
while being omitted from response text. Exact callback binding prevents the
parking renderer from silently changing the admitted prompt. Runtime failures
halt intake; a client disconnect does not undo a completed save or restart an
owner. HTTP headers and bodies have size and total-time bounds.

## What failed or remains uncertain

Review found missing stop-set binding, callback binding, decoded-text checks,
and a header-dribble timeout gap; all were fixed and regression-tested. The
first HTTP test also exposed excessive JSON nesting; its exact failed source
and log are retained. Publisher rendering can trim a reply tail, so reuse
still depends on an exact token-prefix comparison and otherwise prefills.

The interface is local, unauthenticated, sequential, text-only and greedy.
Live native HTTP serving, natural-completion device cases, streaming, tools,
concurrent decode and public deployment are not qualified here. This is not
a cold throughput result or a LocalMaxxing submission.

## Evidence and patches

- [Codec](../experiments/own-xpu-runtime/integration/CHAT-CODEC.md),
  [chat facade](../experiments/own-xpu-runtime/integration/CHAT-SERVICE.md),
  [HTTP adapter](../experiments/own-xpu-runtime/integration/CHAT-HTTP.md).
- [Joined socket replay](../experiments/own-xpu-runtime/integration/receipts/chat-http-replay-cpu-20261023.json),
  [HTTP review](../experiments/own-xpu-runtime/integration/receipts/independent-chat-http-review.json),
  [facade review](../experiments/own-xpu-runtime/integration/receipts/independent-chat-service-review.json).

Run the `test_chat*.py` suite with the existing vllm-xpu Python environment,
which supplies regex and Jinja2, on the helper cores at nice19. No installation
or model loading is needed; the codec reads only the pinned GGUF header.

## When to revisit

The next packet exercises this interface against one admitted native device
owner, checking real rendered-chat append against an in-window fresh reference.
Its checkpoint storage forecast and clean shutdown must pass independently.
