# 6648 r1 closed stale during fresh diagnostic

Date: 2026-08-24. Status: **failed-incomplete; stale before promotion.**

The committed, audited 6648 untreated TP1 r1 packet completed its fresh
hardware gate, model verification, exact canary, graph compilation, and all 25
diagnostic benchmark rows. The post-diagnostic freshness seal then resolved
live vLLM `main` to
`4f686e182a3460b28df9b8e26b377a5069d519fa`, not the built
`6648eb118d77ad001a411cf52f9c6c4719476c83` identity. The runner intentionally
exited 5 before writing a speed gate, starting strict replay A/B, requesting the
quality battery, applying an overlay, or creating an aggregate qualification
result.

This is therefore append-only stale evidence, not a completed TP1
qualification, current record, or speed regression. It does not authorize TP2,
TP4, a compatibility packet, cache promotion, or any change to a protected
speed.

## Completed evidence

The fresh hardware gate passed all 70 manifest entries, including four-device
identity and compute, peer read, four-rank XCCL all-reduce, coherent PyTorch
runtime, root-NVMe health, clean postflight, kernel taint 0, and zero relevant
journal rejects. The arm directly and ordinarily verified all 19 model files,
returned exact canary content `14` with zero cached prompt tokens, and completed
25/25 eligible benchmark rows with cached-token count zero throughout.

An independent audit reproduced these conventional 99-interval diagnostic
statistics:

- median `30.340562433175233 tok/s`;
- p10 `30.310755075111558 tok/s`;
- mean `30.393116548847026 tok/s`;
- minimum / maximum `29.70824382672865 / 30.86004988668125 tok/s`;
- standard deviation `0.2088408924717441 tok/s`;
- legacy inclusive median `30.647032760783066 tok/s`.

The audited median is `0.12276243317523239 tok/s` (about `0.4063%`) above the
frozen diagnostic floor and `0.083662433175231 tok/s` above the protected
diagnostic high. Neither value is replaced: upstream moved before the
preregistered speed-gate write, and no strict A/B or quality result exists.
The authoritative TP1 diagnostic pair remains `30.2178 / 30.2569 tok/s`, and
the strict floor remains `30.31067504052998 tok/s` for both replays.

The newly compiled cache is preservation evidence only: 1,097 files and
147,856,435 file bytes, with manifest SHA-256
`69b723ac8ad82be6df57f16bde8e8790ae3eb49f9fade9cbd3c4392f98538f8a`.
Do not reuse or promote it on a successor head.

## Freshness delta and preservation

The first live successor is one direct commit after 6648:
`[MISC] Cleanup deprecated parameters (#53559)`, 12 files, `+16/-93`. The
change does not touch Qwen dense/XPU semantics, XPU kernels, GDN/mamba,
graph/compilation, speculative decode, distributed/TP, dependencies, or build
files. The packet does not use the removed `VLLM_TRITON_ATTN_USE_TD` alias.
The accepted TP2 78-decision and TP4 152-decision overlays have no textual
source conflict, remain checksum-preserved and disabled, and still require
fresh exact-path/config-hash remapping and full qualification. This bounded
diff lowers porting uncertainty but does not waive the newest-head rebuild.

The campaign root is sealed 98/98 with manifest SHA-256
`4b95642c62582bf4bbc230118e247d1941573d7dcb777918d2e07651b69f6cf2`;
its 21/21 input manifest is
`e9dcc9b8989f6188ea06df69f40fc29d7cf4ddf7077762a3d3140f2e3434fa7e`.
The separate hardware root is sealed 70/70 with manifest SHA-256
`2f316a9b55131e2febaa4e0582075b10f97d24a4be0953f4a7b3322ff6b0379b`.
The candidate container was removed, port `19767` is free, no model server or
render-device holder remains, and the GPUs are idle.

The complete structured closeout is
[`2026-08-24-qwen38-6648eb118d-r1-stale-during-diagnostic.json`](../data/2026-08-24-qwen38-6648eb118d-r1-stale-during-diagnostic.json).
Keep both exact run roots and the frozen packet immutable; do not resume,
overwrite, relabel, or use them as a successor cache.

Next, make the exact 6648 build recoverable on the USB artifact store, verify
every archived image and build-root byte before removing only those exact local
artifacts, then resolve all three upstream identities again. Build the literal
newest vLLM head with exact-current XPU kernels over the live official nightly,
derive a separately named audited zero-overlay TP1 packet, and proceed in order
TP1, TP2, TP4 without lowering any historical floor or discarding accepted
optimization work.
