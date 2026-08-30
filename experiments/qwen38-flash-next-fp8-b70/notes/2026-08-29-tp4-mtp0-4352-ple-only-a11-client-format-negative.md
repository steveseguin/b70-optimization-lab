# Qwen3.8 Flash-Next FP8 TP4 MTP0 A11 client-format closeout

Date: 2026-08-29
Status: infrastructure-negative; no diagnostic result

A11 passed the frozen artifact, source, four-card, XCCL, placement, capacity,
and served-identity gates. All four ranks initialized, model load again reported
31.57 GiB/card, the PLE-only receipt was exact, and the 128-MiB cache exposed
4,747 tokens. The server became healthy without the A8 worker trace.

The diagnostic client then rejected the live stream with `ValueError: each
token event must expose one integer token ID`. It wrote no diagnostic JSON and
therefore retained no complete four-request row, output hash, score array, or
quality/determinism result. No request timing is eligible for speed credit.

Source review of the pinned completion serving path identified the client
mistake. A streaming delta publishes `output.token_ids` as a list and builds
the logprob response over that complete delta; it does not promise that the
list length is one. The parser had imposed a narrower contract than the API.
This is not evidence of a model, runtime, sampler, or device failure.

Supervised cleanup left no owned process, listener, compile root, RPC root, or
device allocation. All four cards returned below 43 MiB and the bounded
journal contains no B70-addressed failure. A11 changes no protected result.

The A12 correction accepts one or more integer token IDs only when token text,
selected-score, and top-score arrays have exactly the same nonzero length. It
still normalizes and validates every generated decision individually. A focused
batched-delta test is added. No server, request, model, score width, or frozen
interpretation changes.

Structured receipt:
[`../data/20260829-tp4-mtp0-4352-ple-only-a11-client-format-negative.json`](../data/20260829-tp4-mtp0-4352-ple-only-a11-client-format-negative.json).
