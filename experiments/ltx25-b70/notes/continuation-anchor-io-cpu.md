# Exact float-anchor I/O helper — CPU evidence, 2026-09-14

[continuation_anchor_io.py](../scripts/continuation_anchor_io.py) implements two
standard-library interfaces, without tensor packages, model access, server
actions, subprocess calls, or writes to state/receipts:

```python
metadata = validate_anchor_bytes(payload, expected_sha256)
payload, metadata = extract_anchor(capture_path)
```

`validate_anchor_bytes` requires immutable bytes of exactly786,432 bytes and a
64-character lowercase SHA256. The declared representation is little-endian
float32 RGB `[1,256,256,3]`. Each scalar's exponent bits are checked for infinity
or NaN; no float conversion, clipping or quantization occurs. Signed zeros,
subnormals, extreme finite values and finite values outside the display range
retain their exact bytes. The error string is constructed only on failure.

`extract_anchor` reads frame24 from the `images` tensor of a regular safetensors
capture. It requires F32 `[25,256,256,3]`, checks an at-most1MiB UTF-8 JSON header,
rejects duplicate keys and nonstandard JSON constants, checks all tensor
descriptors and dtype/shape byte counts, and requires complete nonoverlapping
data-buffer coverage with no holes or trailing bytes. Metadata must map strings
to strings. Unsupported dtypes or shapes outside the bounded parser contract
fail closed. These are narrow capture-reader rules, not a general safetensors
implementation.

The unbuffered reader reads the8-byte header length, the header, and precisely
one786,432-byte frame at its validated offset. It does not read or hash the
whole clip. The same opened descriptor is used throughout, with file
device/inode/size/mtime/ctime checked before and after extraction. Nonregular
inputs, including FIFOs, are rejected without waiting for a writer, and the
descriptor is closed on failure. Ordinary concurrent changes and short reads
fail closed; this is not an adversarial filesystem snapshot guarantee.

Extraction returns the unchanged payload plus its SHA256, shape, dtype, byte
order, source-frame offset, header hash and source file identity. Its metadata
explicitly says the whole capture hash and other frames' finiteness were not
verified. Caller code must bind this capture to the correct predecessor and
compare its expected anchor hash. The source reference is the existing
`LTXBaselineCapture.capture` writer; it stores contiguous raw images under the
`images` safetensors key. Only that Python source was inspected, not a real
capture or model. Its source hash is recorded in the test receipt.

[Thirteen CPU tests](../scripts/test-continuation-anchor-io.py) passed, including
malformed/truncated headers, strict dtype/shape validation, nonzero image
offsets, bad ranges and sizes in all tensor descriptors, overlap/gaps/trailing
bytes, duplicate keys, signed-zero/hash distinctions, nonfinite first/last
samples, bounded reads, simulated concurrent change, and FIFO rejection.
The test files are synthetic sparse captures: a16-byte prefix tensor, the
required images extent with only the anchor materially written, and an8-byte
suffix tensor. The bit patterns are artificial; these checks do not claim
native Torch/safetensors round-trip correctness or generated-image quality.

Reproduce without a tensor runtime:

```bash
python3 experiments/ltx25-b70/scripts/test-continuation-anchor-io.py
```

The [CPU receipt](../data/continuation-anchor-io-cpu-01.json) and
[log](../data/continuation-anchor-io-cpu-01.log) bind these final source hashes:

| File | SHA256 |
| --- | --- |
| `scripts/continuation_anchor_io.py` | `9dffd12ccb90285c5bee32ea7803321822fbf349344073b3dfb63cfac772a2c9` |
| `scripts/test-continuation-anchor-io.py` | `315181946a429f14435fce1b6bed195023e8120b284bbf74b172683eb212c2b5` |

No node registration, runtime packet integration, GPU execution, continuation
replay, audio timing, or speed qualification is included. Host fault restrictions
remain in effect. The parent integration owns node/state wiring and receipts.
