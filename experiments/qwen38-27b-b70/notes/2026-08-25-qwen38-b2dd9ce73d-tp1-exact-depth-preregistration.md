# Qwen3.8 b2dd/1e90 TP1 exact-depth lifecycle r1

Status: **preregistered, not launched; exact image loaded and execution-ready
after live gates**.

The exact b2dd both-current image and its archived build record are present.
Static `--check` validates only the frozen packet; it is not runtime readiness.
Execution still fails closed unless the loaded tag, image ID, embedded source
identity, clean pushed `main`, model, fresh ext4 roots, and idle hardware all
pass their live gates. A substitute or newer image cannot inherit this
identity.

This packet fills the six nonzero active-context cells for one exact identity:
Qwen3.8 27B AutoRound INT4 at revision
`bce40cacab0a4535b92fb3d57615c2bea9adf3d1`, TP1 on GPU 0, MTP0, F16 KV,
and `FULL_AND_PIECEWISE` XPU Graph. It uses the both-current zero-overlay image
built from vLLM `b2dd9ce73dce2ad09007d1db5c171454118981d7` and XPU kernels
`1e90ffa672ba02f17a909da11838a4c55b199783`:

- tag: `neural-download/vllm-openai-xpu:vllm-b2dd9ce73d-kernel-1e90ffa672-official`;
- image ID: `sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296`;
- embedded source identity SHA-256:
  `2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0`.

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
  `/home/steve/qwen38-current-main-runs/tp1-exact-depth-b2dd9ce73d-20260825-r1/01-exact-depths`;
- cache:
  `/home/steve/qwen38-current-main-runs/tp1-exact-depth-cache-b2dd9ce73d-20260825-r1/01-exact-depths`;
- port: `20858`;
- acknowledgement:
  `RUN qwen38-b2dd9ce73d-tp1-exact-depth-20260825-r1 d1-exact-depths r1`.

Retries require a new attempt number, root, cache, and port. No output or cache
is overwritten.

## Interpretation frozen before launch

There is no speed floor. Decode, TTFT, wall rate, and the exact 99-interval
measurement are recorded per depth, but a slow correct point is still a valid
measured cell. This packet cannot lower, overwrite, or relabel any historical
b2dd speed. The protected target-only ledger is hash-checked before launch, and
the receipt states that this exact-context workload is additive evidence under
the dated b2dd profile, never a replacement for the protected short-workload
rate.

A campaign pass means exactly six new measured cells for this one runtime
profile plus a full quality qualification. Any terminal failure or quarantine
is published with its exact evidence and fills only the individual depth rows
whose own receipts pass; it does not license interpolation, inheritance, or a
depth-zero value.
