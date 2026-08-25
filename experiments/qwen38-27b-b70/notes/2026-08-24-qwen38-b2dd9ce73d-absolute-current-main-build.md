# b2dd/1e90 literal-current zero-overlay build

Date: 2026-08-24. Status: **static build and archive pass; GPU
qualification pending.**

The general current-main builder ran once from clean pushed `main` at lab
commit `52a4d01c588472fc06694efe78026cfbbb110bfe`, tree
`25efbd429cf54e28e58e4403c85fb1f2399ea2c3`. It resolved these literal
identities:

- vLLM `b2dd9ce73dce2ad09007d1db5c171454118981d7`, tree
  `65c93c14916a9a895c5592b8a0ba2803efc96346`, package
  `0.26.1rc1.dev1172+gb2dd9ce73.xpu`;
- XPU kernels `1e90ffa672ba02f17a909da11838a4c55b199783`, tree
  `b3cf7a800eea50e0d0f6140c1c2047a074a7fcb9`, package
  `0.1.dev1+g1e90ffa67`;
- official nightly base/index digest
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.

Both zero-source-overlay images passed the builder's wheel identity, import,
extension, Torch-schema, DSO dependency, known pip-check, source-shadowing,
label, and static-receipt gates:

- stock-base-kernel control
  `sha256:a07fca9185f67bb3ccce0d56e2a7be7edc98b0bc90cd98d4c24df13faa8cf6b7`;
- both-current candidate
  `sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296`.

The stock-kernel image is retained as a separately preregistered attribution
control if needed. The first GPU packet uses only the both-current image in the
unchanged three-arm order: fresh diagnostic, strict replay A, strict replay B.

## Upstream provenance

B2dd is nine vLLM commits after the closed 7ca candidate. The range adds CI
reporting and timeout changes, BailingMoeV3 and LFM2-VL fixes, an XD-RoPE
multimodal prefix-cache fix, Qwen3-Next fused QK-norm/MRoPE work, sparse-MLA
XPU metadata synchronization, a NIXL/Mamba ordering fix, and a routed-experts
docstring-only change. The bounded path review found no direct modification to
this lane's `qwen3_5.py`, `qwen3_5_mtp.py`, batch-invariance configuration,
XPU graph capture, or dense Qwen3.5 target path. The potentially adjacent
prefix-cache and multimodal changes are inactive because this packet is
text-only with prefix caching disabled; the Qwen3-Next fused path is not this
model and its optimized implementation is CUDA-only; sparse MLA is not the
dense Qwen3.5 attention path used here. These observations do not waive model
load, source, correctness, quality, graph, or performance qualification.

Kernel 1e90 is the direct successor to the prior baaa kernel. It changes
paged-decode work splitting for head dimensions 512 and 576; this Qwen model's
head dimension is 256. The candidate nevertheless carries a different exact
kernel DSO, so the complete runtime qualification remains mandatory. The
record-grade upstream artifact is workflow run `32798686770`, artifact
`9546354902`, archive digest
`sha256:086116f01e838105167b4dfc408be0b3d4e924d7db9d616a0c00b67a69b24ecb`,
and wheel SHA-256
`f3d999060c11ad6db5b4033d50d19c6b665492380075480d041ec4ee58fdfeb6`.

The source and wheel retain
`vllm/model_executor/determinism/batch_invariant_configs.py` at SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`,
plus `determinism/__init__.py`, `determinism/batch_invariant.py`,
`models/qwen3_5.py`, and `models/qwen3_5_mtp.py`; neither legacy
`model_executor/layers/batch_invariant*.py` member is present. No decision
file, compiled graph, prior-run cache, or source patch was applied.

## Durable build evidence

The aggregate receipt is byte-identical in the ext4 build root and USB archive
at SHA-256
`d56dc84c1137d741042b2e295c6b1f6a40bf28a3c56e0c52761dd725e3a5caa0`.
The 14-file USB `SHA256SUMS` battery passes and has SHA-256
`67d13159a6ec66f1bd17288bef07632be09f963419252f50d47208dc99869997`.
The frozen source-identity JSON is
`2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0`;
the builder and Dockerfile are respectively
`fbc431ed3ee7d5abbf2b952f6733341171b3b84214b0e9cee7d3e052ea404d59`
and `440da02c5438ce76da10e49f665ea9bb3dff6cf1a5c5e2accab2b0612e0e6ead`.
The vLLM source archive is
`063d303afd4ae834b63b7f3d24245c013be937d81146010511dd183b1711dec8`;
the wheel is
`9b59f828266d135dcd1fdf4c868cc3ece0e90cbf393556ae9a61ca5e03b35feb`.

The ext4 build root is
`/home/steve/builds/qwen38-current-main-20260825T023331Z-b2dd9ce73d-1e90ffa672`.
The external archive is
`/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260825T023331Z-b2dd9ce73d-1e90ffa672`.
The tracked receipt is
[`2026-08-24-qwen38-b2dd9ce73d-absolute-current-main-build.json`](../data/2026-08-24-qwen38-b2dd9ce73d-absolute-current-main-build.json).

The accepted TP2 78-file and TP4 152-file decision bundles remain versioned,
disabled, and untouched for exact path/config-hash compatibility remapping
after zero-overlay topology anchors pass.

## Predecessor and launch boundary

The 7ca hardware gate passed and its untreated fresh diagnostic completed all
25 rows at an observed `30.272705632473954 tok/s`, with exact canary `14`, zero
cached tokens, and clean runtime postflight. Its mandatory post-arm freshness
check found vLLM main had advanced, so the runner wrote
`stale-before-promotion` and exited 5 before cache normalization, replay A, or
replay B. The observation is dated stale evidence only: it qualified no
frontier, website cell, decision packet, or TP2/TP4 work. Its machine closeout
is
[`2026-08-24-qwen38-7ca336929c-r1-stale-during-diagnostic.json`](../data/2026-08-24-qwen38-7ca336929c-r1-stale-during-diagnostic.json)
at `a0bf4971bf42276b198547b04bb183bbfc8372058b673b7082d49270da851d37`;
the paired note is
[`2026-08-24-qwen38-7ca336929c-r1-stale-during-diagnostic.md`](2026-08-24-qwen38-7ca336929c-r1-stale-during-diagnostic.md)
at `b83aabd9d2b72f8b0c80a6162fe24059e4992ac1fe4338acc6def3cfa4464331`.

The b2dd packet carries the already-audited 7ca harness unchanged: exact
exit-5 stale reporting and fail-closed normalization plus immutable checking of
the expected empty `dummy_cache` directory. Neither changes server arguments,
graph settings, quality gates, timed work, arm order, or protected performance
floors. No 7ca cache, decision, generated output, or run-root content is an
input.

No GPU, model load, graph compile, benchmark, canary, or quality request ran as
part of this build or packet preparation. At packet drafting the two new run
roots were absent, ports `19812`-`19814` were unbound, and root free space was
`17,226,896 KiB`, above the unchanged `12,582,912 KiB` launch floor. The
post-build recovery pruned exactly `5.623 GB` of unreferenced BuildKit cache
only; all five preserved experiment image IDs stayed unchanged, containers
remained zero, and the immediate post-prune free-space receipt was
`17,228,720 KiB`. The
prebuild storage record
[`2026-08-24-qwen38-09fd-1e90-prebuild-storage-rotation.json`](../data/2026-08-24-qwen38-09fd-1e90-prebuild-storage-rotation.json)
remains exact at
`60a3961d2d1ab007101d5a61794db9ff9e32ea8542594402fa958dbf89654b90`.
It preserves every captured speed and both accepted decision bundles while
documenting the archive-before-delete reserve used for this build.

The eventual wrapper must still recheck every live vLLM, XPU-kernel, nightly,
lab, root-space, container-idle, and process-idle gate immediately before
launch. A newer upstream identity closes this packet stale rather than
weakening a gate or lowering a historical result.
