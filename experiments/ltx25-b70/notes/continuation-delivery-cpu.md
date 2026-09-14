# Exact bounded frame delivery — CPU evidence, 2026-09-14

[continuation_delivery.py](../scripts/continuation_delivery.py) implements
capture verification and exact frame delivery without Torch, NumPy, safetensors
runtime imports, model reads, GPU/server actions, subprocess calls, or footage
writes/deletions. It reuses the frozen
[anchor reader](../scripts/continuation_anchor_io.py) without modifying it.

```python
verification = verify_capture(capture_path, summary_path)
frames = iter_delivery_frames(capture_path, verification, chunk_index)
try:
    for frame_bytes in frames:
        consume(frame_bytes)  # caller owns playback/queue policy
finally:
    frames.close()
```

`verify_capture` checks exactly four F32 tensors against their own capture
summary. Required shapes are images `[25,256,256,3]`, video latent
`[1,128,4,8,8]`, audio latent `[1,8,26,16]`, and waveform `[1,2,48480]`.
The summary must report `torch.float32`, finite values, each SHA256, a48kHz
sample rate, deterministic enabled and warning-only disabled. Its `run_name`
must equal the capture's parent directory name. Summary/header JSON rejects
duplicate keys and nonstandard constants; bounded file/header validation and
all descriptor extents are checked before reading tensor data.

All file read requests are at most65,536 bytes. Every raw scalar is checked
for nonfinite F32 exponent bits, all four tensor hashes are compared with the
summary, and25 separate image-frame hashes are computed. Frame24's hash is
also returned as `anchor_sha256`, matching the frozen anchor helper in tests.
No float conversion or clipping occurs. Captures are held through one regular
file descriptor and their device/inode/size/mtime/ctime identity is checked
during verification. Any mismatch, short read, nonfinite value or detected
change raises an exception without returning partial success.

The returned mapping includes:

- `schema`, `complete`, `run_name`, and `summary_file_sha256`;
- `source_capture_path`, `source_file_identity`, `source_header_sha256`, and
  `source_header_bytes`;
- `tensors`, mapping each name to `dtype`, `storage_dtype`, `shape`, `sha256`,
  `byte_offset`, `byte_length`, and `finite`;
- `frame_sha256`, containing all25 hashes, and `anchor_sha256`;
- `strict_determinism_reported: true`, `sample_rate: 48000`, and
  `byte_order: little`.

`complete` means all four captured tensors matched their supplied summary.
It does **not** mean delivery completed. `delivery_complete` stays false;
`runtime_identity_verified`, `original_reference_parity_verified`, and
`deterministic_replay_verified` also remain false. A capture's own summary
cannot attest the running configuration or establish a reference/replay oracle.
The controller must bind pending run identity and trusted verification output
separately. This distinction is part of the API.

`iter_delivery_frames` requires a full receipt including all25 frame hashes
and exact dtype/shape/range metadata. It snapshots that mapping, reopens the
capture, binds file identity and exact header bytes/ranges, and yields one
immutable786,432-byte F32 frame at a time. Chunk0 yields frames0–24; every
later chunk yields frames1–24, exactly24 newly delivered frames. Each emitted
frame is independently hashed against full verification and bracketed by file
identity checks. Signed zeros, subnormals and finite values outside the display
range remain unchanged. The consumer may retain frames, but the reader holds
only a bounded frame assembly buffer and compact metadata, not the whole clip.

**Successful iterator exhaustion is the delivery completion signal.** The
last yielded frame is followed by a final identity check. Early `close()`
releases the descriptor without reading future frames or asserting completion;
closing after the last yield also does not substitute for exhaustion. Caller
code owns immutable capture storage, trusted receipt provenance and bounded
queues. File metadata checks detect ordinary changes, not adversarial
filesystem snapshots; each delivered frame still has its exact hash checked.

Waveform bytes are verified but not trimmed, resampled, crossfaded or delivered
as an assumed aligned soundtrack. Audio timeline policy remains unresolved.

[Fifteen synthetic CPU tests](../scripts/test-continuation-delivery.py) passed.
They cover four-tensor integrity, strict reported flags, summary/run binding,
signed-zero/finite-bit preservation,25/24-frame delivery, actual read-size bounds,
early close, corrupted final frames, incorrect shapes/dtypes/hashes, source
mutation during verification and delivery, reopened header identity, and the
distinction between the last yield and successful exhaustion. Fixtures have
sparse raw extents and small written integer bit patterns; no real model or
generated capture was read. No native tensor correctness, continuation quality,
audio alignment, throughput, or GPU safety claim follows from these tests.

Reproduce with the standard library:

```bash
python3 experiments/ltx25-b70/scripts/test-continuation-delivery.py
```

The [receipt](../data/continuation-delivery-cpu-01.json) and
[test log](../data/continuation-delivery-cpu-01.log) bind these source hashes:

| File | SHA256 |
| --- | --- |
| `continuation_delivery.py` | `9c126facd3f132f78dc080d9092748a91e4f9671ce93b04db6c3b0828daeaacb` |
| `test-continuation-delivery.py` | `6c6c2e622f961fe446451f3e757fd3a8d7fe00b29e93dd2afeaa1a6f691c0d8e` |
| Frozen `continuation_anchor_io.py` | `9dffd12ccb90285c5bee32ea7803321822fbf349344073b3dfb63cfac772a2c9` |

These helpers change no current runtime packet, fault latch, host setting,
service or model state. The existing host incident still blocks GPU work.
