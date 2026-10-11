# Exact-GDN bundle portability gap

The strict Git-bundle gate remains **blocked** by a preexisting omission and
incomplete recovery declaration. The four archived Laguna bundles now resolve
correctly; no archived member is missing from the logical census. Full inputs,
per-bundle search results and probe logs are retained in
[bundle-portability-gap.json](bundle-portability-gap.json).

The omitted [exact-GDN bundle](../../../patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/vllm-xpu-kernels-q38-gdn-exact-serial-bbae3c5-20260913.bundle)
is 2,565 bytes, SHA-256
`8a8e3fc89cfa405be7a17bb6517091e328adad0fac7566b290d715edfa068d81`.
It advertises `refs/tags/q38-gdn-exact-serial-bbae3c5`, pointing to commit
`bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26`; the recorded target tree is
`e87a7a7a5deba4e816f7e24dbf0b6ccf04c03b2b`. Its required prerequisite is
`e421889999bc1e5a5f11044d14548b9afdba644d`, with recorded tree
`ca6c804765ccb40f5e74d17b665065bd57d9cde7`.

The frozen [inventory v1](../../../data/git-bundle-portability-inventory-v1.json)
lists 58 bundles and omits this artifact. Its existing
[provenance file](../../../patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/vllm-xpu-kernels-q38-gdn-exact-serial-bbae3c5-20260913.provenance.json)
claims `tracked-chain`, but supplies no public base and points to a README and
patch directory rather than an ordered, hash-bound bundle chain. Those source
patches are useful evidence; they are not proof of the required Git identity.
The bundle remains a dependency of the
[exact-GDN recipe](../../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md).

## Bounded recovery checks

- Examined all 31 present tracked kernel/XPU bundles. Imported 30 into a fresh
  temporary bare repository, anchoring each advertised tip and repeatedly
  importing bundles whose prerequisites were available. The exact `e421889…`
  object was absent. Only the target bundle remained unimportable. The JSON
  records every inspected path, SHA-256, prerequisite and advertised ref.
- The main agent queried the recorded public fork,
  `https://github.com/steveseguin/vllm-xpu-kernels.git`; its reported HEAD was
  `0fd18a7c08a64d2645bf083cfa5576200b61b02c`. An exact prerequisite fetch failed
  with `upload-pack: not our ref e421889999bc1e5a5f11044d14548b9afdba644d`.
  The error log's contents and SHA-256 are embedded in the JSON. The HEAD
  observation was reported separately and is not part of that error log.
- The tracked patch series retains changes and author information. Rebuilding
  an identical tree does not establish the original commit's full metadata
  and parent chain. No replacement commit identity was accepted.

This does not show that the object is absent from every external source or
backup. Protected originating runtime/source trees were not inspected. No GPU
work, source build or runtime change occurred.

## Strict gate and recovery requirement

```bash
python3 -B tools/validate-git-bundle-inventory.py \
  --inventory data/git-bundle-portability-inventory-v1.json --repo-root .
```

The recorded exit code is **2**: only the exact-GDN bundle is unlisted, and
`absent=[]`. Archive-aware offline regression tests can pass while this actual
repository-wide portability check correctly fails.

Recover the exact prerequisite commit, its trees/blobs and required ancestry
from the originating source repository or a verified backup. Then prove the
existing bundle restores the recorded tip/tree in a disposable repository and
add a hash-bound public or tracked recovery contract. Only then create a
successor inventory and run the public prerequisite proof. Keep the frozen
53-entry legacy digest, historical bundle, old provenance and v1 bytes intact.
No claimed recoverable v2 was created, no matching-tree commit was substituted,
and no exception was added to make the gate pass.
