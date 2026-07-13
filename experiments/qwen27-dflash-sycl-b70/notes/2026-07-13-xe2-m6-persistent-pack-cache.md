# Xe2 M6 persistent Q4_0 pack cache

## Result

Implemented and populated the persistent disk cache for all 187 Q4_0 tensors
used by the promoted Xe2 width-6 experiment: 130 gate/up tensors and 57 down
tensors from layers 8-64. The earlier 130-payload set remains preserved.

The artifact is outside Git at:

```text
/mnt/usb-models/model-packs/qwen27-xe2-m6-v2/
  7fb8a0192d10819de692735c398e01037c89023fac3f9ac54e17bb6633c321c3/
```

It contains 187 independently addressed payloads in the exact
`q4_0-xe2-dpas-v2` layout, a set manifest, and an exact runtime index. Total
payload size is `9,375,252,480` bytes (`8.73 GiB`); each tensor is
`50,135,040` bytes.

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
independent scalar transform exactly. The promoted slot table is checked
exactly: gate/up use slots 0-129 and down layers 8-64 use slots 130-186. The
finished 187-tensor disk set and staged RAM copy both passed deep SHA-256
verification.

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

The full 187-tensor extension measured:

| Operation | Result |
|---|---:|
| Incremental prepare | `27.2 s` wall |
| Existing gate/up imports | `130`, each payload SHA-256 checked and hard-linked |
| New down packing | `57` tensors; `16.85 s` pack counter |
| Full disk deep validation | `7.21 s` for `9,375,252,480` bytes |
| First RAM stage | `10.45 s`, including new disk trust |
| RAM copy portion | `3.12 s` |
| Hot trusted RAM lookup | `0.0108 s` |
| Full RAM deep validation | `7.37 s` |

## Commands

```bash
python3 scripts/qwen27-xe2-m6-pack-cache.py inspect

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/qwen27-xe2-m6-pack-cache.py prepare

python3 scripts/qwen27-xe2-m6-pack-cache.py verify \
  --set-key 7fb8a0192d10819de692735c398e01037c89023fac3f9ac54e17bb6633c321c3

python3 scripts/qwen27-xe2-m6-pack-cache.py verify --deep \
  --set-key 7fb8a0192d10819de692735c398e01037c89023fac3f9ac54e17bb6633c321c3

python3 scripts/qwen27-xe2-m6-pack-cache.py stage-ram \
  --set-key 7fb8a0192d10819de692735c398e01037c89023fac3f9ac54e17bb6633c321c3

python3 scripts/qwen27-xe2-m6-pack-cache.py stage-validate \
  --set-key 7fb8a0192d10819de692735c398e01037c89023fac3f9ac54e17bb6633c321c3
```

`prepare --skip-source-hash` deliberately trusts the SHA-256 already recorded
in the tracked model manifest. It is for repeated local development only.

The first `stage-ram` created a durable `deep-validation.json` receipt tied to
the exact disk manifest SHA-256 and canonical payload table. It then copied to
a same-tmpfs staging directory and atomically renamed the completed set into
place. Later startup lookups compare that receipt, manifest identity, all 187
canonical keys, file sizes, and a device/inode/mtime stat-identity table without
rehashing 8.73 GiB. Changing the disk manifest or replacing/modifying a payload
invalidates the receipt and forces a fresh deep validation.

After staging the full set, `/dev/shm` retained `34,478,022,656` bytes. The
tool keeps at least 8 GiB free by default and recorded both cold-stage and
hot-lookup results beside the disk manifest.

## Runtime loader boundary

The tool emits `runtime-index.tsv`, whose full byte identity covers the exact
model, BMG architecture, layout, 187 slots, payload SHA-256 table, tensor
names/shapes/types, sizes, and paths. The guarded protected-source loader uses
`GGML_SYCL_XE2_Q4_M6_PACK_CACHE` to consume this trusted stage. It validates the
complete fixed index, projection contract, payload size, and BMG device before
upload, and automatically falls back to the existing CPU packer on any
mismatch. The staging helper remains the SHA-256 trust boundary so startup
does not rehash 8.73 GiB.

The runtime deliberately does not rehash each 50 MiB payload. The environment
must therefore point only at the atomic stage produced and deep-admitted by
this helper; `/dev/shm` is writable and is not treated as intrinsically
immutable.

### Runtime smoke and isolated startup A/B

The rebuilt BMG-AOT server consumed the full stage successfully:

- 65 gate, 65 up, and 57 down payloads loaded from the trusted stage;
- `187` trusted loads, `0` host pack probes, `0` CPU packs, and `0` cache
  rejections;
- exact response parity against the cache-off control on a fixed greedy
  request: `101 103 107 109 113`, SHA-256
  `705db84c7b9200ee383dc8b25a3c74fae8fb46d2cae3b62c730f98292129b018`;
- both paths accepted `17/20` DFlash draft tokens on that request; measured
  decode was `76.42` versus `76.78 tok/s`, consistent with initialization-only
  behavior.

After the GPU2 capture worker stopped, a same-GPU1, same-binary, same-flags A/B
measured:

| Boundary | CPU pack | Trusted RAM pack | Delta |
|---|---:|---:|---:|
| First eligible pack | `3.555877 s` | `3.561348 s` | `+0.005471 s` |
| Last uploaded eligible pack | `26.565232 s` | `22.709907 s` | `-3.855325 s` |
| Eligible-pack window | `23.009355 s` | `19.148559 s` | `-3.860796 s` |
| Model ready | `28.900031 s` | `25.158409 s` | `-3.741622 s` (`-12.95%`) |

The selected cache run again had exactly `187/0` trusted/CPU loads. One prior
isolated cache attempt reached model-ready at `34.169901 s` because a single
`blk.54.ffn_down.weight` upload stalled for `5.394 s`; it is retained as
variance evidence rather than hidden. The immediate clean repeat still had a
similar one-time `5.292 s` stall, but the CPU control's pack window also
contained comparable uninstrumented allocation/runtime delay. The paired
boundary timestamps, not the sum of per-payload read/copy timers, are therefore
the startup comparison.

Evidence logs:

- cache:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/xe2-m6-full187-packcache-gpu1-isolated-repeat-20260713.log`;
- CPU control:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/xe2-m6-full187-cpupack-gpu1-isolated-20260713.log`;
- retained anomalous cache attempt:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/xe2-m6-full187-packcache-gpu1-isolated-20260713.log`.

This cache changes initialization and experiment iteration time, not decode
throughput, and is not headline benchmark evidence.
