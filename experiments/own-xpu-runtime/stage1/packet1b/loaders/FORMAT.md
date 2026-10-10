# Packet 1b format arithmetic

These are independent CPU readers/decoders, not a ggml runtime import or a
translation of its C dequantization functions. No model payload was acquired.
GGUF is a separate future storage lane; packet 1 still rejects GGUF as a
replacement for the official FP8 target.

## Sources and data boundary

The [official GGUF specification](https://github.com/ggml-org/ggml/blob/ffa4e8b80930029a35991f94e7c8a93cd67730ab/docs/gguf.md)
defines the container: header, typed metadata, fastest-first tensor dimensions,
tensor type identifiers, relative offsets and aligned data section. It does
**not** fully specify the quantization bit layouts or IQ codebooks. Claiming
all nine numerical decoders come from that document alone would be incorrect.
The supplement used here is the pinned upstream format declarations in
[ggml-common.h](https://github.com/ggml-org/llama.cpp/blob/e3546c7948e3af463d0b401e6421d5a4c2faf565/ggml/src/ggml-common.h),
[type/size declarations](https://github.com/ggml-org/llama.cpp/blob/e3546c7948e3af463d0b401e6421d5a4c2faf565/gguf-py/gguf/constants.py),
and the packing diagrams and mathematical format interpretation in
[gguf-py/quants.py](https://github.com/ggml-org/llama.cpp/blob/e3546c7948e3af463d0b401e6421d5a4c2faf565/gguf-py/gguf/quants.py).
These were read for format research. The scalar element-index implementation
in [dequant.py](dequant.py) and synthetic field packers are newly written;
no ggml dequantization code or runtime tree is copied or imported.

The 256-entry `iq3xxs_grid` is normative format data, retained as
[iq3-grid.json](iq3-grid.json), with its source revision and source-file hash.
Each integer encodes four little-endian magnitude bytes. The 16 IQ4 levels are
also normative format data. Both tables are credited to ggml/llama.cpp
contributors under their [MIT license](FORMAT-DATA-LICENSE.txt), retained with
the data. IQ3 signs are derived by even parity, not a copied sign table.
[Source evidence](../source-evidence.json) pins every inspected source blob.
No learning/optimization algorithm, generated weights or codebook fitting is
performed here.

Safetensors follows the [official format](https://github.com/huggingface/safetensors#format).
Eight prefix bytes give the little-endian JSON length. Tensor offsets are
relative to the end of that JSON. Packet 1b admits exactly packet 1's BF16 and
E4M3 storage and requires complete contiguous payload coverage. The parser
reads only prefix and header; file size validates payload extents but does
not authenticate payload hashes.

## GGUF type table

| ID | Type | Elements/block | Bytes/block | Stored fields, in byte order |
| ---: | --- | ---: | ---: | --- |
| 1 | F16 | 1 | 2 | IEEE binary16 |
| 30 | BF16 | 1 | 2 | upper 16 bits of IEEE binary32 |
| 8 | Q8_0 | 32 | 34 | F16 scale, 32 signed int8 codes |
| 11 | Q3_K | 256 | 110 | 32 high-mask bytes, 64 low-code bytes, 12 packed scale bytes, F16 scale |
| 12 | Q4_K | 256 | 144 | F16 scale, F16 minimum scale, 12 packed scale/min bytes, 128 nibble bytes |
| 13 | Q5_K | 256 | 176 | Q4_K prefix, 32 high-bit bytes, 128 nibble bytes |
| 14 | Q6_K | 256 | 210 | 128 low-nibble bytes, 64 high-two-bit bytes, 16 signed scales, F16 scale |
| 18 | IQ3_XXS | 256 | 98 | F16 scale, 64 grid indices, eight 32-bit sign/scale words |
| 23 | IQ4_XS | 256 | 136 | F16 scale, 16 high-scale bits, four low-scale bytes, 128 nonlinear nibble codes |

All multi-byte fields are little endian. Version 3 is required; big endian,
other versions, other types (including F32), nested metadata arrays, zero-size
tensors and row widths not divisible by their block size fail closed.
Container limits are 32 MiB of metadata/tensor info, 1,000,000 metadata/tensor
entries, rank at most four, positive power-of-two alignment at most 1 MiB,
and signed-63-bit byte arithmetic. Supported metadata scalars are all twelve
standard scalar/string types; arrays may contain scalars or strings.
`split.no`, `split.count`, `split.tensors.count` are validated together and
across shards. Filenames do not select a decoder.

## Element equations

`d` and `m` below are F16 values widened exactly to FP32. Every multiply and
subtract rounds separately to FP32, without FMA. Index decoding is integer
arithmetic; output follows the file's contiguous element order. These are
mathematical format values, not a claim that an eventual packed GPU GEMV has
this reduction order.

- **Q8_0:** `d * signed_code`.
- **Q3_K:** sixteen groups of 16 share signed six-bit scales `s = code - 32`.
  Low scale nibbles occupy bytes 0–7 for groups 0–7 and high nibbles of those
  same bytes for groups 8–15. Bytes 8–11 carry the two high scale bits in four
  planes. Two 128-element halves use four low-two-bit planes over 32 lanes;
  eight high-mask planes cover the eight 32-element groups. A clear mask bit
  subtracts four from the low code. Value: `(d * s) * q`.
- **Q4_K/Q5_K:** eight groups of 32 have unsigned six-bit scales/minima. The
  first four scale/min bytes hold low six bits for groups 0–3 and high two
  bits for groups 4–7. The last four bytes carry low four scale bits and low
  four minimum bits for groups 4–7. A 64-element group stores its first 32
  nibbles low and next 32 high. Q5 adds one high bit per element from eight
  planes over 32 lanes. Value: `((d * s) * q) - (m * minimum)`.
- **Q6_K:** each 128-element half uses 64 low-nibble bytes, first 64 values low
  and next 64 high, with four two-bit planes over 32 lanes. Subtract 32 from
  the reconstructed six-bit code. Signed int8 scales apply to consecutive
  groups of 16. Value: `(d * s) * q`.
- **IQ4_XS:** eight groups of 32 have signed six-bit scales, encoded with bias
  32. Consecutive groups share low-scale nibbles; two-bit high scales are in
  the 16-bit field. Each group's first 16 codes use low nibbles, the remaining
  16 high nibbles. Value: `(d * s) * IQ4[code]`.
- **IQ3_XXS:** each group of 32 has eight four-value grid indices and one word.
  The top nibble gives `s`; the remaining 28 bits hold four seven-bit sign
  codes. Each sign code's eighth sign bit makes even parity. Value:
  `((d * (0.5 + s)) * 0.5) * grid_magnitude * sign`. Indices are not uniform
  three-bit signed integers. Signed zero from multiplication is preserved.

Tests pack representable logical values, decode them and compare every value.
They include nonzero scales/minima, signed scales, every bit plane, all 256
IQ3 indices, all 128 sign codes, literal byte fixtures, multiple blocks, and
invalid byte counts. This is a round trip through the *representation*, not
an assertion that lossy quantization recovers arbitrary original FP32 weights.
