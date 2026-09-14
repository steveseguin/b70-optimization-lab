# Native RMS compiler packet04 prepared, inactive

2026-09-14. The separate `prepare-native-rms-runtime.py` builder derives
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-04`
from immutable compiler packet03. It does not launch, reload, contact, or modify
the running server. It imports only standard-library source/runtime-metadata
checkers, never Torch or the new backend. No GPU operation occurred.

The parent manifest is explicitly pinned to
`9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980`.
The backend input `ltx_native_rms_backend.py` is pinned to
`09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb`.
The builder checks these and the original adapter/node/checker identities before
copying, then checks parent and mutable input hashes again before sealing.

The sole adapter execution change is:

```python
self.compiled = compiler(block, backend=make_backend(
    OPTIONS, Path(os.environ['LTX_ENCODER_RUN_DIR']) / 'native-rms-graphs',
    expected_count=15), fullgraph=True, dynamic=False)
```

`OPTIONS` is unchanged; it is bound inside the backend, with no outer compiler
`options` argument. The backend rewrites the selected block's RMS graph nodes to
opaque native RMS calls before Inductor. This is a new compiler intervention,
not a claim that the previous compiler candidate passed its native exact gate.
The expected replacement count is15 per graph; the original two native stage
checks and all full-clip gates still must pass.

Two necessary imports are added to the adapter. The compiler node's hardcoded
adapter hash is updated in both its helper and custom-node copies; their
remaining AST is identical. The node continues to import the one adapter module
from `source/scripts`, which imports the one backend module from that directory.
The new checker retains the original encoder-parent checks, adds immediate
compiler-parent inheritance checks, and extends the server identity inventory
with the backend. The schema is `ltx.compiler-native-rms-runtime-packet.v1`.

Exactly four inherited files change: the packet-local checker, adapter, and the
two identical compiler-node copies. All launcher bytes, server flags, original
OPTIONS, block/lifecycle/registration guards, graphs, native model sources,
decoder sources, loader sources, and every other inherited file remain exact.
No decoder extent patch or loader-memory candidate is included.

The whole adapter AST, after reversing just the two imports and compiler-call
change, equals the original. Node AST equality after reversing its hash literal
also passes. The new checker verified all1238 inventory files, all immediate
parent inheritance constraints, original encoder ancestry, graph constraints,
extension copies, backend pin, and unchanged runtime metadata. These are source
checks only, not native operator, block, full-clip, or speed qualification.

Artifacts:

- Packet04 manifest SHA256: `c4e0f7e56fc7bbc51101894d79d279dd9886f07272868dc99cc7953c647a65c9`
- Effective adapter SHA256: `d3daa4a7b7150a4fa316c346fdea259139147419a59950642bf06b2ec62fe3d4`
- Builder SHA256: `dbe470120c3ecd5f6f0f42786958494acf8e99b8dc693540f0289495b13e6db6`
- Exact source delta: `patches/native-rms-backend-runtime-04.patch`
- Preparation receipt: `data/native-rms-runtime-04-preparation.json`
- Manifest copy: `data/native-rms-runtime-04-manifest.json`
- Source-check receipt: `data/native-rms-runtime-04-source-checks.json`

The packet archives the immediate parent manifest and the four original changed
files under `provenance/native-rms-parent/`. It also retains all prior provenance
and failed-candidate artifacts. Existing packet paths are never overwritten.

To reproduce source preparation, select a new unused packet name; the existing
04 path is immutable:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B \
  /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/prepare-native-rms-runtime.py \
  --output /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-UNUSED_NAME
```

Use a lowercase safe suffix in place of `UNUSED_NAME`. Preparation grants no
runtime admission. Root owns final review, the native results, any single
controlled application reload, and the subsequent bounded campaign. The old
compiler clients hardcode the original adapter hash and cannot qualify packet04;
a separately pinned successor client must bind the new adapter/backend identity
and validate the RMS graph receipts. No client is changed by this builder.
