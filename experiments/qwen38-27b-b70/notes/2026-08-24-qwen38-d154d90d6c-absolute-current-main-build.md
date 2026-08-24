# d154 literal-current zero-overlay build

Date: 2026-08-24. Status: **static build and archive pass; GPU
qualification pending.**

The general current-main builder ran once from clean pushed `main` at lab
commit `583395843`. It resolved and retained these literal identities through
the post-archive freshness seal:

- vLLM `d154d90d6c4bcf26a0c78ac4f3e43621c14333ba`, tree
  `6310c33970329a4e4a9683ab7c94c1f4573a6cc8`, package
  `0.26.1rc1.dev1161+gd154d90d6.xpu`;
- XPU kernels `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`, package
  `0.1.dev1+gbaaa05bb4`;
- official nightly base/index digest
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.

Both zero-source-overlay images passed wheel identity, import, extension,
Torch-schema, DSO dependency, known pip-check, source-shadowing, label, and
static-receipt gates:

- stock-base-kernel control
  `sha256:51ceafc2ffed75e0a7f1166b6cd55251516502363a9d00d12fe0ad4b3469e70b`;
- both-current candidate
  `sha256:358fb358a30463ededcb9ead252d0841b29eeeac684be756e16528329cb1030e`.

The full d154 upstream commit is present, including its new optional Model
Runner V2 batch-sharded sampling implementation and Qwen3.5 model hook. That
option defaults off and is not enabled in the protected single-request
baseline. It is reserved for a separately preregistered multi-request TP
experiment, where it can be assessed without changing the existing TP speed
identity.

The literal source, wheel, installed package, image labels, import receipt,
source identity, and aggregate build receipt all bind
`vllm/model_executor/determinism/batch_invariant_configs.py` to SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`.
Both former `model_executor/layers/batch_invariant*.py` members are rejected.
No decision file, compiled graph, old cache, or source patch was applied. The
accepted TP2 78-file and TP4 152-file decision bundles remain versioned and
untouched for compatibility remapping after the zero-overlay anchors pass.

The aggregate receipt is byte-identical in the ext4 build root and USB archive
at SHA-256
`024a1ceb228ff0c60a2ae6ddfe05a23615ba33da3fc05841e8ceb4cf8f694e1e`.
The 14-file USB `SHA256SUMS` battery passes and has SHA-256
`3a00ab8f5c35a8086b8e860e6764c67de1a45205c591f69f62baefeaeb34bf6e`.
The tracked receipt is
[`2026-08-24-qwen38-d154d90d6c-absolute-current-main-build.json`](../data/2026-08-24-qwen38-d154d90d6c-absolute-current-main-build.json).

Docker image export temporarily reduced root free space to `1,709,128 KiB`.
The adopted swap-by-digest protocol restored the qualification reserve without
touching evidence: unused builder cache reclaimed a reported `7.652GB`, then
only the two already-stale, never-run 0d image IDs were removed. Their complete
source/build archives remain; no byte-for-byte Docker tar had been created, so
recovery must rebuild and revalidate rather than assume the historical image
ID. The d154 images and official base remain exact, Docker has no container,
and root free space returned to `14,897,124 KiB`. The structured rotation
record is
[`2026-08-24-qwen38-0d7d5ed0b2-storage-rotation.json`](../data/2026-08-24-qwen38-0d7d5ed0b2-storage-rotation.json).

No GPU, model load, graph compile, benchmark, canary, or quality request ran.
This creates no speed claim and changes no protected result or floor. The d154
packet must re-resolve vLLM, XPU-kernel, nightly, and lab identities at launch.
If they remain exact, qualify the both-current zero-overlay TP1 lane without
lowering its gates; only a full pass and any required fresh TP1 decision packet
authorize TP2 zero-overlay/78-decision work and then TP4
zero-overlay/152-decision work.
