# TP1 6a9-compatible stock-kernel decision overlay r1

Status: test-only and unqualified. No arm has used this packet, and it makes
no performance or promotion claim.

This bundle preserves the 38 `.best_config` decisions from the fully
qualified vLLM-`0ecc284790` / stock-base-kernel TP1 cache. A read-only census
against the completed untreated vLLM-`6a9c69fa85` TP1 cache found all 38
relative paths and all 38 embedded `configs_hash` values compatible. It is
therefore eligible for one separately preregistered decision-only test on
6a9; it is not evidence that the older winners will be faster there.

The source decision bytes are unchanged from the historical packet. Their
manifest remains
`b941bb71c1d264dcd55104b106b2dff6a85c686776b072e0ef6cc18a8354c928`.
The row-level census is [`compatibility-census.tsv`](compatibility-census.tsv),
SHA-256
`f3477beba643f0136d71388e54a3a539ab067b716a7db9750b0131b457b03d03`.
It records source and target file hashes, embedded configuration-set hashes,
canonical normalized-selection hashes, equality, and byte identity for every
path.

## Compatibility result

The source and 6a target have:

- 38 source decisions, 38 target decisions, and 38 common relative paths;
- 38/38 matching embedded `configs_hash` values;
- 24 equal and 14 different normalized winner selections;
- two byte-identical files and 36 files differing in winner or metadata;
- the same code hash `fb13d4aa1ef8a386c76ab56d39925ff4de083895d9dcbd136e778046e78bb118`;
- the same compiler hash `ddcad03736`; and
- a byte-identical computation graph, SHA-256
  `f493f62d98181193e6760136123c70511e9a0a7f1d91cbf3243008a619553339`.

The cache namespace and config/environment factors changed, so no compiled
artifact is portable. The historical outer/AOT namespaces were
`d65565f7e2` / `68fc8c632858eb7c65d6de5b3d4f347cb96e1b18357ec6468847d6c7010adc9d`;
the 6a namespaces are `1698e8221e` /
`3be24aa9230ff903e8d2dc977dbd63e1cdac51c2f9086ca264135826fd81d61b`.
The config factor changed from `7fd9f3bcb2` to `006ac9802b`, and the canonical
environment SHA-256 changed from
`58a8631879b3855c3c1a408d3dad33d48f66b17f7541f08d51d3f1030d7baceb`
to `a048dd409b16d2004c6ec4c534e0e954c304ed2cd5bebe6d8bc39be9cb7d7c7b`.

Normalized selection means canonical compact JSON after removing
`configs_hash`, `found_by_coordesc`, `time_taken_ms`, and
`triton_cache_hash`. Those fields describe the compatible search space or
tuning provenance rather than the selected launch configuration.

## Qualification boundary

A future runner may copy only these 38 decision JSON files into the exact 6a
AOT namespace of a nonexistent ext4 cache, then require a fresh compile. It
must not copy the untreated cache, generated Python, kernels, binaries,
Triton artifacts, AOT models, model metadata, or an outer cache.

The packet remains unqualified until a fresh diagnostic and two sealed strict
replays pass the frozen TP1 speed, model, canary, quality, cache, source,
host, repository, and freshness gates. The protected diagnostic floor stays
`30.2178 tok/s`; the strict floor stays `30.31067504052998 tok/s`. A miss is
preserved and does not authorize TP2, lower a floor, or overwrite a prior
high.

Verify the preserved source bytes with:

```bash
cd source
sha256sum -c ../manifest.sha256
```

See [`metadata.json`](metadata.json) for the exact source, parent-result,
cache-identity, census, and qualification contracts.
