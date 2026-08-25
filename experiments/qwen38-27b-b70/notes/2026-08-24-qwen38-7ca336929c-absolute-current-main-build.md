# 7ca literal-current zero-overlay build

Date: 2026-08-24. Status: **static build, archive, and independent artifact
audit pass; GPU qualification pending.**

The general current-main builder ran once from clean pushed `main` at lab
commit `52a84620b4244a0e685b768f213c5de744ca21ac`, tree
`023cf954e3c0cf43f09f40d8d2ca0996fb85f262`. It resolved these literal
identities:

- vLLM `7ca336929c169fee1210dd5293029d78811fba27`, tree
  `af3fde0a669bcd73274ff9e2cfd410ea69c92ee6`, package
  `0.26.1rc1.dev1163+g7ca336929.xpu`;
- XPU kernels `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`, package
  `0.1.dev1+gbaaa05bb4`;
- official nightly base/index digest
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.

Both zero-source-overlay images passed the builder's wheel identity, import,
extension, Torch-schema, DSO dependency, known pip-check, source-shadowing,
label, and static-receipt gates:

- stock-base-kernel control
  `sha256:6043c332c753604a827f75c07f480998c1330e9e722b3120a8e6b3c47f74fc6c`;
- both-current candidate
  `sha256:b7bc798035552130e96f3649c21541f1b40fa3c5db0558631e44e461297196a4`.

## Upstream provenance

7ca is the direct child of `a0f1b9ad`, which is the direct child of the dated
d154 candidate. The intermediate a0f commit changes one FLEX_ATTENTION CI-test
tolerance. The 7ca commit removes ten deprecated model architectures and their
registrations, tests, examples, and documentation: 46 paths, 49 insertions,
and 6,620 deletions relative to a0f. A path-level review found no direct change
to the Qwen3.5, Qwen3.5-MTP, batch-invariance/determinism, or XPU files used by
this lane. The subsequent independent source/wheel/receipt artifact audit
passed; model load, quality, source freshness, and performance remain mandatory
runtime gates rather than inferred from that static result.

The source and wheel inspected while drafting retain
`vllm/model_executor/determinism/batch_invariant_configs.py` at SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`,
plus `determinism/__init__.py`, `determinism/batch_invariant.py`,
`models/qwen3_5.py`, and `models/qwen3_5_mtp.py`; neither legacy
`model_executor/layers/batch_invariant*.py` member is present. The optional
batch-sharded sampling implementation inherited from d154 remains default-off
and is not enabled by this protected single-request packet. No decision file,
compiled graph, prior-run cache, or source patch was applied.

## Durable build evidence

The aggregate receipt is byte-identical in the ext4 build root and USB archive
at SHA-256
`e090d5a7694ffa6f595d84e6adc38a3da6cd33020e5c7f4d96ae678ecd146622`.
The 14-file USB `SHA256SUMS` battery passes and has SHA-256
`6f146518cf10167c7d34e8ca6dab1b133bb6cbca698984917cff72f97ef30863`.
The frozen source-identity JSON is
`e215141578bd8abd16edda382be622a2af00597e7f319910a66cd089904e8cf0`;
the builder and Dockerfile are respectively
`cb1260b00c877420bd847adcebd022504b6ed58643ec8c5740ff8336dd8f549a`
and `440da02c5438ce76da10e49f665ea9bb3dff6cf1a5c5e2accab2b0612e0e6ead`.
The vLLM source archive is
`cd02fc69f71c422faf4d1b40631ae34194a442b2f370af5a7c335f688171f760`;
the wheel is
`84c3a92c9ae421e153a835cd6b66a73f3dc4b6f0317097b29650fbcc7bda6abd`.
The tracked receipt is
[`2026-08-24-qwen38-7ca336929c-absolute-current-main-build.json`](../data/2026-08-24-qwen38-7ca336929c-absolute-current-main-build.json).

The accepted TP2 78-file and TP4 152-file decision bundles remain versioned,
disabled, and untouched for exact path/config-hash compatibility remapping
after zero-overlay topology anchors pass.

## Predecessor and launch boundary

The d154 hardware gate passed. Its untreated fresh diagnostic passed at
`30.35213813941521 tok/s`; strict replay A completed its workload and quality
battery at an observed `30.3562353617713 tok/s`. It then stopped
`stale-before-promotion` because vLLM main advanced during the arm, before its
strict speed-gate file or replay B could be created. A post-close audit also
found the independently disqualifying addition of an empty
`vllm/dummy_cache` directory after the frozen directory set. D154 therefore
qualified no frontier, website cell, TP1 decision packet, or TP2/TP4 work.
Its machine closeout is
[`2026-08-24-qwen38-d154d90d6c-r1-stale-during-replay-a.json`](../data/2026-08-24-qwen38-d154d90d6c-r1-stale-during-replay-a.json)
at `00a2ced82c7787417a1e7205323ffdb530da3d84b9092939501727c85392de37`;
the paired note is
[`2026-08-24-qwen38-d154d90d6c-r1-stale-during-replay-a.md`](2026-08-24-qwen38-d154d90d6c-r1-stale-during-replay-a.md)
at `9c176d2eb3fe33741c55bac53745b2b8b3784d6c336a85fa2ce2e6e04dad9eb4`.

The 7ca successor packet carries only two bounded harness corrections from
that closeout: semantic reporting of the exact exit-5 stale state, and explicit
normalization plus immutable checking of the expected empty `dummy_cache`
directory. Neither changes server arguments, graph settings, quality gates,
timed work, or protected performance floors.

No GPU, model load, graph compile, benchmark, canary, or quality request ran as
part of this build. It creates no speed claim. At initial packet drafting the
two new run roots were absent and ports `19812`-`19814` were unbound, while root
free space was below the unchanged `12,582,912 KiB` launch floor. The sealed
storage rotation then removed only the two exact superseded d154 image IDs,
retained both 7ca images, recorded zero running containers before and after,
and restored root free space to `14,081,388 KiB`. No performance evidence,
protected speed, runtime/launcher configuration, or TP2/TP4 bundle changed.
The rotation record is
[`2026-08-24-qwen38-d154d90d6c-storage-rotation.json`](../data/2026-08-24-qwen38-d154d90d6c-storage-rotation.json)
at `ed5d77bb12910ceaf0121c905ed6b597976a743f0e0eec4cc69f857f1622eab0`.
The capacity, privileged container-idle, and independent artifact-audit
blockers are therefore closed. The eventual wrapper must still recheck every
live vLLM, XPU-kernel, nightly, lab, root-space, container-idle, and
process-idle gate immediately before launch.
