# Qwen3.8 4af/1e90 TP1 exact-depth lifecycle r1

Status: **preregistered, not launched; exact image currently unavailable**.

The 2026-08-25 archive audit did not find the recorded 4af two-image transfer
bundle on attached storage, and the both-current 4af image is not loaded. The
packet is therefore not presently runnable. Static `--check` validates only
the frozen packet. Execution remains blocked and must fail closed until the
exact tag and image ID below are restored; a substitute image, b2dd image, or
newer build cannot inherit this identity. A later b2dd exact-depth campaign
may reuse the lifecycle design only as a separately pinned packet.

This packet fills the six nonzero active-context cells for one exact identity:
Qwen3.8 27B AutoRound INT4 at revision
`bce40cacab0a4535b92fb3d57615c2bea9adf3d1`, TP1 on GPU 0, MTP0, F16 KV,
and `FULL_AND_PIECEWISE` XPU Graph. It uses the both-current zero-overlay image
built from vLLM `4af586e185b028acf08312a4dee381b5998a137e` and XPU kernels
`1e90ffa672ba02f17a909da11838a4c55b199783`:

- tag: `neural-download/vllm-openai-xpu:vllm-4af586e185-kernel-1e90ffa672-official`;
- image ID: `sha256:cb8e41a716a896fdc641d85df1339eb7cc72db9185db5df7f08292ef9e5f1e3f`;
- embedded source identity SHA-256:
  `f89a02ca59a8ed0079e2297863b0c2799ae8f4665c3fd921e3ddf4c5409bb41a`.

The run does not qualify another runtime, image, topology, quantization, MTP
depth, KV dtype, or graph mode.

## Frozen measurement

One newly started server uses a fresh ext4 output root and fresh ext4 compile
cache. Its configured maximum length is `32896`, covering the deepest exact
input (`32768`) plus the fixed 128-token output window. The launcher sends the
tracked flat-token fixture at these depths, in this order:

`2048, 4096, 8192, 16384, 24576, 32768`.

Each request must prove the exact fixture/case/input hash, `usage.prompt_tokens
== D`, cache zero, no prompt truncation or context shift, 128 returned output
IDs, a length finish, and the conventional first-100-event / 99-interval rate.
All six requests run in the same server. A failure is retained in the aggregate
receipt and prevents the campaign from passing; it never becomes an estimate.

Depth zero remains **missing**. Its frozen fixture case is an empty token array,
and the OpenAI-compatible client deliberately refuses to replace that with a
one-token request. Merely configuring a context capacity does not measure any
active-context cell.

After the six exact-depth requests, the same server must pass the full frozen
quality battery: seven exact cases, eight same-server repeats with one unique
hash, the 8K needle, all 24 baseline comparisons, and all 16 cache observations
at zero. Server startup must also prove quantization identity, non-eager engine
mode, both PIECEWISE and FULL graph capture markers, and graph-capture
completion.

## Lifecycle and gates

The launcher is inert unless `--execute` is combined with the exact printed
acknowledgement. Execution additionally requires clean pushed `main`, frozen
file hashes, the exact local image and embedded source identity, direct model
verification, no active container/model/render-node owner, a free port, fresh
roots on ext4, and the host/GPU lifecycle locks. It writes one atomic terminal
stage receipt after strict cleanup and a post-run local Git check. A live
remote advance after launch is recorded but cannot mutate the already frozen
server, image, inputs, or local checkout.

The r1 locations are:

- output:
  `/home/steve/qwen38-current-main-runs/tp1-exact-depth-4af586e185-20260825-r1/01-exact-depths`;
- cache:
  `/home/steve/qwen38-current-main-runs/tp1-exact-depth-cache-4af586e185-20260825-r1/01-exact-depths`;
- port: `19858`;
- acknowledgement:
  `RUN qwen38-4af586e185-tp1-exact-depth-20260825-r1 d1-exact-depths r1`.

Retries require a new attempt number, root, cache, and port. No output or cache
is overwritten.

## Interpretation frozen before launch

There is no speed floor. Decode, TTFT, wall rate, and the exact 99-interval
measurement are recorded per depth, but a slow correct point is still a valid
measured cell. This packet cannot lower, overwrite, or relabel any historical
b2dd speed. The protected target-only ledger is hash-checked before launch, and
the receipt states that this later 4af profile is separate evidence.

A campaign pass means exactly six new measured cells for this one runtime
profile plus a full quality qualification. Any terminal failure or quarantine
is published with its exact evidence and fills only the individual depth rows
whose own receipts pass; it does not license interpolation, inheritance, or a
depth-zero value.
