# 4af/1e90 literal-current zero-overlay build

Date: 2026-08-25. Status: **static build and archive pass; GPU qualification
pending.**

The current-main builder produced two zero-overlay images from vLLM
`4af586e185b028acf08312a4dee381b5998a137e`, XPU kernels
`1e90ffa672ba02f17a909da11838a4c55b199783`, and official nightly base
`sha256:c345345f9dcc751983a77cef128783513f2994fdd334e5cd382aeea36a2e0a36`:

- stock-kernel control image
  `sha256:5c5bde2a8a2484336b08c7c852281ea95a547c8aa43f8f764b5bc993d9b21680`;
- both-current zero-overlay image
  `sha256:cb8e41a716a896fdc641d85df1339eb7cc72db9185db5df7f08292ef9e5f1e3f`.

Both images passed wheel and source identity, source-shadow rejection, rebuilt
Rust identity, all required XPU extension imports, required Torch schemas, ELF
dependency/RPATH checks, and the exact known pip-check exceptions. This build
uses the v3 fail-closed preflight: a SHA-pinned Python file is executed as a
real legacy-Docker build command, and the image plus post-build runner both
require a nonempty import receipt. The previous heredoc form could be skipped
by the legacy builder and is not equivalent evidence.

The aggregate receipt SHA-256 is
`328bf6727262174345f6bb571752c44a77a36b00c2946c5ef6e9fba4cff68989`;
source identity is
`f89a02ca59a8ed0079e2297863b0c2799ae8f4665c3fd921e3ddf4c5409bb41a`.
The final external archive checksum manifest is
`372e45c70b1013f3d1c5c371ce945a6e29b639bf60d2c221fbde06d387c05dbf`
and its full battery passed. Durable artifacts are under
`/mnt/extended-ssd/steve-archive/qwen-current-main-builds-20260825/20260825T061034Z-4af586e185-1e90ffa672`.

That directory also contains the exact two-image transfer bundle
`images-4af586e185.docker.tar.zst`: `5,399,932,281` bytes, SHA-256
`4da6fd4601a1a1a6dda80b7854fa2edee5c5443afa38a9ff1506a6fb75c33db4`.
The compressed stream passed `zstd -t`; its Docker manifest contains exactly
the two tags above; and a same-daemon `docker load` round trip retained both
image IDs. Recover it on the measuring host with:

```bash
zstd -dc images-4af586e185.docker.tar.zst | docker load
```

Relative to the qualified b2dd snapshot, the direct Qwen-adjacent runtime
change is a DFlash2 decoder-layer loading fix. This packet's staged TP1 matrix
still uses `qwen3_next_mtp`, not DFlash2, and no DFlash checkpoint is supplied,
so that fix is not credited as a measured speed improvement. The remaining
runtime changes are unrelated model/config work; none waives model load,
correctness, quality, acceptance, graph, topology, or performance gates.

This host launched no GPU, model, server, benchmark, or quality request. The
tracked build receipt is
[`2026-08-25-qwen38-4af586e185-absolute-current-main-build.json`](../data/2026-08-25-qwen38-4af586e185-absolute-current-main-build.json).

The frozen b2dd matrix remains the active measured campaign: TP1 context and
eager-MTP0 passed, and the eager-MTP2 sensitive parent passed with exact target
oracle agreement and `589/868` accepted draft tokens. Its next authorized work
is the full MTP2 short battery, followed by one eager-MTP4 actual only if that
battery passes. The b2dd TP2 packet remains ready and TP4 remains qualified.
This 4af pair is a separate later-snapshot control/candidate packet and must
not inherit those results.
