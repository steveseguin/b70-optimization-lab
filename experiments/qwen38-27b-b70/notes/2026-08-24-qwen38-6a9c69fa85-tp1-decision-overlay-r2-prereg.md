# 6a9c TP1 decision-overlay r2 qualification preregistration

Date: 2026-08-24. State: **preregistered, unexecuted**.

## Goal and boundary

Test whether the exact path- and `configs_hash`-compatible TP1 autotune
decisions preserved from the qualified stock-kernel lane restore the protected
TP1 performance class on literal-current vLLM
`6a9c69fa851389dcf1ee5d3a2363e27af665d26d`, exact-current XPU kernels
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, and official nightly digest
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.

This is a narrow performance-preservation packet on the way to TP2, TP4, and
the wider neural.download matrix. It does not alter or revert upstream source,
the image, a DSO, a generated kernel, a compiled object, the model, or any
protected measurement. The exact immutable image remains
`sha256:f86c4c78d76a484f5d54eda310419c91a2471634ab97782022ef7573fc19a7d9`
with source overlay `none`; the only candidate treatment is a separately
labeled runtime `.best_config` decision overlay.

R1 passed this treatment's seeded-fresh diagnostic at
`30.268740193465128 tok/s` and then stopped before strict replay A only because
an unrelated remote lab documentation commit advanced during the atomic run.
The local commit, frozen inputs, engine source, image, decisions, cache, and
measurement did not change. R2 therefore retains every engine and performance
gate while correcting that lab-control category error: live lab equality is
mandatory at launch; during model arms, the clean local commit and frozen
inputs are immutable, while live vLLM, XPU-kernel, and nightly identities
remain continuously gated. A remote-only lab commit cannot mutate a running
image and is not an in-arm abort condition.

## Frozen completed parent

The only authorized parent is the closed untreated campaign at
`/home/steve/qwen38-current-main-runs/tp1-untreated-6a9c69fa85-20260824-r1`.
It ran once and ended with controlled exit 10 and exact root state
`complete-speed-only-regression-no-overlay-run`. Its sealed identities are:

- campaign evidence manifest SHA-256
  `ecc882372a9408ede3e660d56a6ed9e986adf2d748199e9caa331fd57ef00e10`;
- aggregate result SHA-256
  `fc4c81bdf75dd632c60bde47865272e5f63a0a21e457abe5de4bc2cc9ef2b213`;
- frozen input manifest SHA-256
  `e493930467912721f58422afef5a6ebe2494bae1288f251500efe4536a17b28b`;
- immutable 1,097-file compiled-cache manifest SHA-256
  `4a41a96bb1ddb9c5a96d476c11bca89278742a61f9b20aace40cfbcec39364a4`;
- original hardware-gate manifest SHA-256
  `b15e94a256fcc4870edfa21240d0230fcd4ee7a7329cc33feb2a81f5f01cadbe`;
- host kernel `7.0.0-30-generic` and boot
  `086de284-0771-4269-9cb2-e064fe303e40`.

The parent diagnostic passed at `30.27858669748398 tok/s`. Strict natural-EOS
replays A/B measured `30.26782494070049 / 30.27119782672338 tok/s` and both
missed the unchanged `30.31067504052998 tok/s` floor. Every non-speed gate
passed: exact model verification and canaries in all arms, realistic cache-zero
benchmark shape, full quality and 24/24 baseline comparisons, exact source and
image identity, immutable replay cache, clean kernel/runtime/container/port
postflight, and same prompt order. The wrapper must verify the complete sealed
parent evidence and the actual parent cache bytes before exposing a GPU.

The parent is read-only evidence. This program cannot append to it, resume it,
replace it, or call its old wrapper. A new current-commit hardware gate is
required because the lab commit now contains the separately reviewed successor
packet.

## Frozen failed predecessor

The decision-overlay r1 roots are sealed predecessor evidence and are never
resumed or reused:

- campaign
  `/home/steve/qwen38-current-main-runs/tp1-control-decision-overlay-6a9c69fa85-20260824-r1`;
- hardware gate
  `/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-6a9c69fa85-overlay-20260824-086de284-venvlib-r1`;
- campaign manifest SHA-256
  `3098ab384aea4f76995498f8f8a83eb93732b4b61aa5e80dd4ee3df5d21f8196`;
- frozen-input manifest SHA-256
  `db58dad8b6f5be7d26703abbd8652d2c8ead4d11e4599091e376c9b07e8bc5ca`;
- failure JSON SHA-256
  `e03a24950951e1ab2b3dc0658ec4bc0a95b085d84c9c277e25be3823c4b1bb00`;
- diagnostic benchmark SHA-256
  `4c81b37d145372ec491ac0d7fc1f4b4e944b5e4ada9276ba936e6d670d07917e`;
- 497-file cache-manifest SHA-256
  `9f9f4e03dc3fb023ec66f983789834424e69bd0351b32e7502beae0a5113347e`;
- 139-directory manifest SHA-256
  `c27d308f3721467d344d89fa9fcee333bea20e9bddbac35603217d6d3c6b9298`.

Its exact final state is `failed-incomplete mode=all rc=1`; strict A, strict B,
and an aggregate result are absent. The tracked closeout JSON and note hashes
are respectively
`c9b20b3360fc24c45a8f116cb6b2f6c7cca12b66d842475e13fb71a62c983e5b`
and `286525a8017c03bf09c69f8f290a5bf2b36da1673130331550a0f3ca3b1d4d57`.
R2 must verify this predecessor before GPU exposure, then create an entirely
new cache. No r1 compiled file is transferred.

## Exact compatibility census and candidate

The freshly derived candidate is
`experiments/qwen38-27b-b70/autotune-winner-overlays/tp1-6a9c69fa85-stock-kernel-best-config-compatible-r1/`.
It maps the historical stock-kernel decision source against the sealed 6a9c
cache beneath AOT namespace
`3be24aa9230ff903e8d2dc977dbd63e1cdac51c2f9086ca264135826fd81d61b`.
The census found all 38 relative paths on both sides and 38/38 equal embedded
`configs_hash` values, with no missing, extra, or incompatible path. Two files
are byte-identical to the untreated 6a9c selections. After removing loader and
search-provenance metadata, 24 winner selections are equal and 14 differ. That
mapping authorizes copying all 38 historical decision records unchanged; it
does not predict a speed win.

The packet contains exactly 38 regular `.best_config` JSON payloads. Its
payload manifest SHA-256 is
`b941bb71c1d264dcd55104b106b2dff6a85c686776b072e0ef6cc18a8354c928`.
Its metadata SHA-256 is
`33606d3d0f93a31e4d68b430414116e39cb6bb394dc1f3a5c5dfb3c1bfcb5b29`,
compatibility-census SHA-256 is
`f3477beba643f0136d71388e54a3a539ab067b716a7db9750b0131b457b03d03`,
and README SHA-256 is
`09c5ac484afea6e9b5aedd3822d4af1b69ea35ec0c9b80da16910007386b72cc`.
No compiled cache, `.py`, `.so`, binary, AOT model, generated kernel,
modelinfo, lock, or XDG file is part of the candidate.

## Fixed atomic roots and cap

The only allowed invocation is the full atomic wrapper with `all` (or no
argument). It has no resumable arm modes and no overridable campaign roots.
The exact roots are:

- fresh hardware gate:
  `/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-6a9c69fa85-overlay-20260824-086de284-venvlib-r2`;
- overlay result:
  `/home/steve/qwen38-current-main-runs/tp1-control-decision-overlay-6a9c69fa85-20260824-r2`;
- wholly new ext4 compile cache: `overlay-cache` beneath that result root.

Both roots and the cache must be absent. The program uses ports
`19789`-`19791`, locks all four B70s for the current-commit hardware gate, and
then runs at most three serialized TP1/GPU0 model arms. It must start from an
accelerator-runtime-clean environment, clean pushed `main`, the fixed boot,
the exact two local images, the exact recovered build receipt and archive, and
live remote vLLM, XPU-kernel, and nightly identities matching this packet.

The fresh hardware gate must pass four-device identity, compute on every card,
the peer-read oracle, four-rank XCCL allreduce, coherent Torch runtime, healthy
root NVMe, taint and kernel-delta checks, lock handoff, and repository
postflight. A source, kernel, nightly, image, boot, local lab commit, frozen
input, or dirty-worktree change stops the packet stale. A remote-only lab ref
advance after launch is recorded later and cannot mutate the running identity.

## Cache treatment and fixed runtime identity

The seeded-fresh arm starts with a nonexistent ext4 cache. The runner may
create only the exact target AOT/inductor path and copy the 38 preregistered
decision JSON files to their exact relative paths. Before compilation it must
prove that the cache contains exactly those 38 files and no other artifact.
It must then compile the graph and executables from scratch, prove that it did
not directly load a prior AOT model, and require these freshly generated cache
identities:

- outer namespace `1698e8221e`;
- AOT namespace
  `3be24aa9230ff903e8d2dc977dbd63e1cdac51c2f9086ca264135826fd81d61b`;
- code hash
  `fb13d4aa1ef8a386c76ab56d39925ff4de083895d9dcbd136e778046e78bb118`;
- compiler hash `ddcad03736`;
- config hash `006ac9802b`;
- canonical environment SHA-256
  `a048dd409b16d2004c6ec4c534e0e954c304ed2cd5bebe6d8bc39be9cb7d7c7b`;
- computation-graph SHA-256
  `f493f62d98181193e6760136123c70511e9a0a7f1d91cbf3243008a619553339`.

The compiler, workload, and shutdown must leave all 38 decision bytes
unchanged and create no additional `.best_config` record. The complete fresh
cache is checksum-frozen after the diagnostic arm. Replays A and B must begin
and end byte-identical to that entire cache. No file from the parent's compiled
cache is transferred.

All model arms use target-only MTP0, F16 model/KV, 32K maximum context, TP1 on
GPU0, graph `FULL_AND_PIECEWISE` with capture sizes `[1,2]`, one sequence,
1,024 batched tokens, memory utilization 0.90, async scheduling, prefix cache
off, chunked prefill on, and `PYTHONHASHSEED=0`.

## Three conditional model arms

1. Seeded-fresh diagnostic on port `19789`: 25 unique cold prompts, 512
   generated tokens, EOS ignored. It must pass every model, canary, benchmark,
   cache, GPU, graph, image, freshness, and cleanup gate and reach the unchanged
   `30.2178 tok/s` diagnostic floor. A speed miss closes the packet without a
   replay.
2. Exact-cache strict replay A on port `19790`: natural EOS plus the complete
   quality battery. It must reach `30.31067504052998 tok/s`, pass seven exact
   cases, eight deterministic repeats, the 8K/7,617-token needle, all 24
   baseline comparisons, cache-zero checks, and cache immutability. A speed
   miss closes the packet without replay B.
3. Exact same-cache strict replay B on port `19791`: natural EOS, the same
   benchmark and all non-quality-arm gates, the unchanged strict floor, and
   complete cache immutability.

Every arm retains returned token IDs and conventional 100-event/99-interval
accounting. Replay A/B full-array and first-100 agreement is reported but
remains non-gating, matching the parent contract; exact prompt ID order is a
non-speed gate. A non-speed failure stops immediately and is classified
separately from a clean speed miss. Every
terminal pass, complete negative, non-speed failure, and unexpected incomplete
failure must have an atomic root status plus checksum-sealed evidence.

## Frozen interpretation

- If all three overlay arms pass, this exact 38-decision packet is qualified as
  a versioned runtime overlay for the exact 6a9c/kernel/nightly/image/boot
  identity. It preserves the frozen TP1 speed and quality contract and
  authorizes the separately preregistered TP2 zero-overlay plus compatible
  78-decision remap. It does not replace any historical TP1 measurement.
- The untreated parent and overlay are on the same boot and exact runtime
  image, but they are sequential rather than randomized/interleaved. A pass
  qualifies the resulting configuration; any stated causal uplift must retain
  that timing limitation.
- If the diagnostic arm has a non-speed-clean speed miss, preserve it as a
  complete negative and explicitly record that the full quality battery did
  not run. If strict replay A or B has a quality-clean speed miss, preserve
  that complete negative. Do not lower a floor, retreat to older active source,
  or advance TP2.
- If a non-speed gate fails, preserve that distinct failure and do not infer a
  performance regression.
- If vLLM main, XPU-kernel main, official nightly, either exact image, the host
  boot/kernel, local lab commit, frozen inputs, parent/predecessor evidence,
  decision bundle, or protected ledger changes before or during execution,
  stop stale or failed. Require the clean pushed local lab commit to equal live
  `origin/main` before launch, but do not abort an arm because a remote-only lab
  ref later advances. Rebuild or rederive compatibility against a newer engine
  base; never blindly carry the decisions.
- TP4 remains downstream of TP2 and must retain its accepted 152-decision
  packet and fixed 0.60 memory utilization. Nothing here authorizes applying
  TP1 settings wholesale to TP2 or TP4.
