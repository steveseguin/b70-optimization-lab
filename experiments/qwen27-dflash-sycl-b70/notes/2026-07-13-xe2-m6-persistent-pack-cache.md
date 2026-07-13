# Xe2 M6 persistent Q4_0 pack cache

## Result

Implemented and populated the persistent disk cache for all 130 Q4_0 gate/up
tensors used by the guarded Xe2 width-6 experiment. Protected llama.cpp source
was not changed.

The artifact is outside Git at:

```text
/mnt/usb-models/model-packs/qwen27-xe2-m6-v2/
  942dc71558357d09724a74525383255c0cd1387216e45c147632876e962d17ac/
```

It contains 130 independently addressed payloads in the exact
`q4_0-xe2-dpas-v2` layout plus a set manifest. Total payload size is
`6,517,555,200` bytes (`6.07 GiB`); each tensor is `50,135,040` bytes.

## Identity and validation

`scripts/qwen27-xe2-m6-pack-cache.py` parses the GGUF directory without
copying or modifying the source model. Tensor cache keys cover:

- target-model SHA-256;
- tensor name, shape, and GGML type;
- pack layout version;
- target architecture `bmg-g31`.

The admitted target SHA-256 is
`20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a`.
Every tensor manifest preserves a source-tensor SHA-256 and packed-payload
SHA-256. Publication uses a same-filesystem temporary file followed by atomic
rename, so interrupted work is resumable without admitting partial payloads.

The vectorized transform was checked byte-for-byte against a direct scalar
translation of the protected runtime pack formula on a synthetic Q4_0 tile.
The first real gate tensor's first quant tile and scale tile also matched the
independent scalar transform exactly. The finished 130-tensor set then passed
deep SHA-256 verification.

## Measured initialization cost

Measurements used the 15 GB target GGUF and the external USB artifact root:

| Operation | Result |
|---|---:|
| First full model SHA-256 | `8.558 s` |
| First vectorized packing, 130 tensors | `37.792 s` |
| Cached prepare, full source SHA-256 retained | `8.76 s` wall; `0` tensors repacked |
| Cached prepare, trusted recorded source hash | `0.17 s` wall; `0` tensors repacked |
| Cached shallow set/key/size admission | `0.04 s` wall (`0.0028 s` internal) |
| Cached deep SHA-256 of all 6.07 GiB | `5.10 s` wall (`5.058 s` internal) |
| First atomic RAM stage, including new disk deep trust | `7.549 s` |
| RAM payload copy portion | `2.264 s` |
| Hot repeated `stage-ram` lookup | `0.06 s` wall (`0.00867-0.00890 s` internal) |
| Hot `stage-validate` lookup | `0.05 s` wall (`0.00478-0.00483 s` internal) |
| Explicit deep RAM validation | `5.35 s` wall (`5.308 s` internal) |

The first-pack timing excludes the per-tensor SHA-256 time from its reported
`37.792 s` pack counter; checksums were still completed before publication.
Use the cached shallow check for rapid trusted development lookup and the deep
check at loader admission or whenever artifact integrity is uncertain.

## Commands

```bash
python3 scripts/qwen27-xe2-m6-pack-cache.py inspect

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/qwen27-xe2-m6-pack-cache.py prepare

python3 scripts/qwen27-xe2-m6-pack-cache.py verify \
  --set-key 942dc71558357d09724a74525383255c0cd1387216e45c147632876e962d17ac

python3 scripts/qwen27-xe2-m6-pack-cache.py verify --deep \
  --set-key 942dc71558357d09724a74525383255c0cd1387216e45c147632876e962d17ac

python3 scripts/qwen27-xe2-m6-pack-cache.py stage-ram \
  --set-key 942dc71558357d09724a74525383255c0cd1387216e45c147632876e962d17ac

python3 scripts/qwen27-xe2-m6-pack-cache.py stage-validate \
  --set-key 942dc71558357d09724a74525383255c0cd1387216e45c147632876e962d17ac
```

`prepare --skip-source-hash` deliberately trusts the SHA-256 already recorded
in the tracked model manifest. It is for repeated local development only.

The first `stage-ram` created a durable `deep-validation.json` receipt tied to
the exact disk manifest SHA-256 and canonical payload table. It then copied to
a same-tmpfs staging directory and atomically renamed the completed set into
place. Later startup lookups compare that receipt, manifest identity, all 130
canonical keys, file sizes, and a device/inode/mtime stat-identity table without
rehashing 6.07 GiB. Changing the disk manifest or replacing/modifying a payload
invalidates the receipt and forces a fresh deep validation.

`/dev/shm` had `50,371,276,800` bytes available before staging and
`43,853,557,760` bytes (`40.84 GiB`) afterward. The staged directory occupies
`6,517,706,815` bytes including metadata. The tool keeps at least 8 GiB free by
default and recorded both cold-stage and hot-lookup results beside the disk
manifest.

## Remaining runtime boundary

The artifacts are mmap-safe and loader-addressable, but llama.cpp still needs
a checksum-aware binding from each gate/up tensor to its corresponding cached
payload. The integration must fail closed on any key, size, checksum, layout,
architecture, or model-identity mismatch. This cache improves initialization
and experimentation; it does not by itself change decode throughput and is not
headline benchmark evidence.
