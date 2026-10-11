# Stage 2 packet 2 — IQ3 GGUF loader and packed SYCL kernels

**CPU exactness passed; SYCL compiled and linked; no device execution.**
Prepared on `steve-b70s`, October 11, 2026 UTC. The own runtime's first real
model target is now **Qwen3.8 Flash-Next UD-IQ3_XXS (Unsloth), quantized
compressed version, on two B70s**. The 27B FP8 stage remains documented.
Owner direction: “setting up and optimizing the iq3 model is what we want to
do, yes, and doing our own inference engine for it is allowed also.”

This is our own implementation. Its oracle is the CPU decoding of this model's
own bytes, not an FP8 tolerance. No full-model output, speed, GPU exactness,
fit, or lossless runtime claim follows from this packet.

## Implemented

[loader/gguf.cpp](loader/gguf.cpp) reads GGUF v3 little-endian headers,
all standard scalar/string metadata and nonnested arrays, tensor descriptors
and all three split ordinals (including this release's metadata-only shard).
It checks UTF-8, duplicate names/keys, counts, rank, integer overflow, block
rows, alignment, overlap, file extents and complete split coverage. Header
reads use exact-size `pread` calls with a 32 MiB limit: no stream read-ahead
into weights. Unknown numerical types fail closed.

Loading parses directories only; it copies no tensor payload. `Slice` owns a
read-only `MAP_PRIVATE` mapping and a shared file descriptor, aligns the mmap
start to the OS page size, and exposes the exact requested byte span. There is
no `MAP_POPULATE`, eager full-file read, dequantized weight shadow, or implicit
host-pinning. A slice survives its originating `Shard`; moving it transfers
the mapping. Bounds and file-size checks happen before mmap. Backing files
must remain immutable for the lifetime of mappings; fstat cannot protect
against another process truncating an already mapped file.

`Model` checks every descriptor against the generated packet-1 census plan,
and independently binds component, layer and placement to admitted GGUF name
patterns, including the globally named PLE table owned by layer 1. The plan
is generated from the pinned in-repository census by the CPU test/control
plane; arbitrary files are not authenticated merely by parsing. Real header
hashes match the [existing complete payload admission](../../../qwen38-flash-next-ud-iq3xxs-b70/packet1/admission-receipt.json).
This packet does **not** rehash 82 GB while the independent baseline reads it.
Native model admission must bind the full payload identity and immutability
again; small sampled reads do not reauthenticate unsampled weights.

`Model::reserve` reserves packed weights through the existing
[Device/Arena owner](../../stage1/packet3-prep/src/owner.hpp), with `weights`,
process lifetime and component/name labels. It refuses host-only lookups and
wrong logical-card ownership. Logical card 0/1 to physical `Device` mapping
is supplied by the future executor; this loader does not select or enumerate
cards. Header inspection never calls reserve. Full-model upload, admission of
working memory, host lookup scheduling and the decoder graph remain later
packets. The native test uploads only small owned fixtures through Arena
pinned slabs and the existing bounded CopyEngine.

| Placement | Packed bytes |
| --- | ---: |
| Card 0: layers 0–23, plus replicated HC down/up | 26,506,330,880 |
| Card 1: layers 24–47, full head/final norm, plus replicated HC down/up | 26,798,288,640 |
| Both cards, combined | **53,304,619,520** |
| Host file-backed PLE | 28,800,138,240 |
| Host file-backed token embedding | 521,472,000 |

Every layer's 512 experts stays together on its assigned card. This is a new
explicit layer placement preserving packet 1c's extra 675,430,400-byte HC
accounting allowance. It is not a measured TP2 layout or throughput claim;
removing unused HC replicas needs a later plan revision. File backing is not
resident RAM. KV stays full 16-bit; KV, recurrent state, graph/workspace,
activation copies and driver shadows still need admission. These GGUF shards
contain no MTP block.

[kernels/math.hpp](kernels/math.hpp) implements IQ3_XXS, IQ2_S, Q3_K, Q8_0,
F16/BF16, **plus IQ3_S, IQ4_NL, Q6_K and F32 needed by the actual model**.
The recipe name is not a tensor type: the admitted files contain zero
IQ3_XXS, Q3_K or F16 tensors. Those three formats have synthetic evidence only.
[kernels/device.cpp](kernels/device.cpp) supplies block dequantization, M=1
packed GEMV and routed-expert packed GEMV for all ten types.

The shared header contains the exact per-element block equations, scale and
sign handling, casts, lane dot product and CPU tree. Device code includes it
directly. Dequant output is FP32 for comparison; GEMV reads F16/BF16
activations, dequantizes packed weights into FP32 registers, accumulates
FP32, then rounds once to the requested F16/BF16 output (BF16 default).
No hidden BF16 weight-rounding boundary is inserted. This defines this
packet's arithmetic; it does not yet establish full-layer/operator parity
against another inference engine.

Thirty-two logical lanes consume columns `lane, lane+32, ...` in ascending
order, starting at +0. Each product and add rounds separately. The tree adds
adjacent partial groups of widths 1,2,4,8,16, with barriers between device
stages; no floating atomic or implementation-selected subgroup reduction.
One workgroup owns one row. Both physical subgroup 16 and 32 variants compile
with the same arithmetic order. This is a correctness-first implementation:
repeated packed-byte/index accesses, codebook loads and barriers may prevent
reaching bandwidth roofline. No performance has been measured.

Routes are `Route{expert_id,row_begin,row_count}` in an **Arena device
allocation**, with an input vector per route and fixed output span. Submission
rejects host/pinned pointers, freed or aliased bindings and insufficient
extents. The kernel reads the descriptor on device and validates expert ID
and row span before computing a bank address. Invalid routes set status 1 and
canonical-NaN outputs without reading bank/input; unused tail rows are NaNs.
The future test changes route IDs/spans and activation signs, including
invalid descriptors. There is no host routing dereference in the kernel.

The small owner extension adds `Device::compute` and an internal
`SyclOperation` hook. Allocation handles and dependencies are checked and
compute events enter the **same** one-queue ledger as copies. Shutdown drains
compute before freeing weights or staging. No application queue is borrowed.
The historical packet3 native smoke remains evidence for its old identity;
this new compute interface has only mock and compile evidence today.

## CPU results and build identity

[CPU receipt](cpu-receipt.json), [build receipt](build-receipt.json),
[test runner](tests/run_cpu.py) and [build driver](validate.py) retain inputs,
hashes, source identities, exact commands, compiler commands and outputs.

- **282,880 FP32 dequant values bit-exact**, including signed-zero checks and
  full index coverage for the three IQ codebooks in synthetic fixtures.
- **148 GEMV rows bit-exact** at the FP32 accumulator and final 16-bit output,
  against an independently evaluated Python FP32 fixed-order reduction using
  `stage1/packet1b/loaders/dequant.py`; 37 fresh executable-process repeats
  reproduce every output byte.
- Real samples: **81,680 packed bytes**, four consecutive rows from one tensor
  of each of the seven present types. Tensor names, absolute offsets, raw
  hashes and decoded/output hashes are retained. Wider model shapes and all
  expert payloads are not claimed covered by these seven samples.
- All **65,536** bit patterns each for F16/BF16 widening; **115,141** finite
  FP32 output-cast cases including half midpoints and adjacent values.
- Complete **1,224-tensor** real header/census parity, all three header hashes,
  synthetic typed metadata/splits/mmap, malformed inputs and forged placement
  rejection. Each suite reads about 44.10 MB of headers including independent
  parser/hash/model checks; no complete tensor or shard is scanned.
- All **512 expert IDs**, valid/invalid row spans and F32 special bit patterns
  checked on CPU; tracked compute lifetime/dependency tests pass with mocks.
- Existing resource-owner **12/12** host regressions pass; **7/7** fault-watcher
  tests pass with a fake child and fake journal. Neither invokes a GPU.

Compiler: installed **icpx 2026.0.0 (20260331)**, C++20, release `-O3`,
`-fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee`, plus `-fsycl` on
native translation units/link. Builds use nice19, OMP_NUM_THREADS=2 and two
jobs. IEEE nearest-even is the arithmetic contract; dynamic rounding modes
and floating-point exception trapping are not used. Initial strict-mode
compilation was rejected by the SYCL target; development failures and fixes
are listed in the receipt. The device executable and SYCL static library
**compile and link**, including both subgroup variants. Device JIT/execution
and device denormal behavior remain unverified. The executed host binary
has no SYCL, Level Zero, Unified Runtime or OpenCL dependencies.

Reproduce with installed tools only (build outputs and fixtures are deleted
after receipts are written):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet2/validate.py
```

`--keep-build` retains only the packet's ignored `build/` directory for a
later authorized device window. It still runs **only CPU tests**. Final
preparation left no scratch/build tree. No GPU execution/enumeration, device
node, server, Docker, systemd, port 8188, LTX unit, download, host-setting
change or write under `/mnt/usb-models` occurred.

## Packed-byte bandwidth floors

These are **calculated lower bounds, not measured or predicted latency** at
507–537 decimal GB/s on one card. [roofline.py](roofline.py) regenerates the
complete per-layer and per-shape [table](roofline.json) from the admitted
census. For a single sequential request the layer split does not divide a
layer's latency by two. Counts exclude extra HC replica traffic, KV/state,
activations, codebook/cache traffic, routing, computation, launch costs,
collectives and host lookup I/O.

| Layer class | Packed active bytes/layer | Floor at 507 GB/s | Floor at 537 GB/s |
| --- | ---: | ---: | ---: |
| Ordinary GDN (34 layers) | 92,186,496 | 0.181827 ms | 0.171669 ms |
| Layer 1, including PLE projections | 127,289,216 | 0.251064 ms | 0.237038 ms |
| Layer 2, upgraded expert grids | 106,722,176 | 0.210497 ms | 0.198738 ms |
| QSA (12 layers) | 87,867,392 | 0.173308 ms | 0.163626 ms |

Typical selected expert: two IQ2_S gate/up matrices, each 640 rows × 2560
columns at **820 B/row**, plus IQ4_NL down 2560 × 640 at **360 B/row**.
Ten experts read 19,712,000 B/layer. Layer 2's IQ3_S gate/up rows are
1,100 B, giving 23,296,000 B for ten expert triplets.

| Format and row width | Packed bytes/row |
| --- | ---: |
| IQ3_XXS, 2560 (synthetic-only format here) | 980 |
| IQ2_S, 2560 | 820 |
| IQ3_S / Q3_K, 2560 (Q3_K synthetic-only here) | 1,100 |
| IQ4_NL, 640 | 360 |
| Q6_K, 2560 / 6144 | 2,100 / 5,040 |
| Q8_0, 320 / 640 / 2560 / 10240 | 340 / 680 / 2,720 / 10,880 |
| F16 / BF16, 2560 (F16 synthetic-only here) | 5,120 |
| F32, 2560 | 10,240 |

## First device window

[WINDOW.md](WINDOW.md) gives the bounded one-card exactness test, its command,
fault watch and pass criteria. The command is prepared, **not executed**.
The first window needs an exclusive, separately authorized card and fresh
health admission; ongoing baseline work owns its cards. Its result cannot
be substituted with this CPU pass.

## Format credit

Container layout follows the pinned
[GGUF specification](https://github.com/ggml-org/ggml/blob/ffa4e8b80930029a35991f94e7c8a93cd67730ab/docs/gguf.md).
The specification alone does not define IQ codebooks or all bit layouts.
The lab's [FORMAT.md](../../stage1/packet1b/loaders/FORMAT.md) and
[dequant.py](../../stage1/packet1b/loaders/dequant.py) supply the retained
independent equations and exact pinned ggml/llama.cpp format-research credit.
`grids.hpp` contains only generated literal normative format tables from
those three JSON files, credited to ggml/llama.cpp contributors under their
[retained MIT license](../../stage1/packet1b/loaders/FORMAT-DATA-LICENSE.txt).
`generate_grids.py` reproduces the table bytes and tests enforce equality.
No ggml kernel, runtime implementation or baseline source tree is copied or
linked. Unsloth supplies the separately pinned mixed-quantization model.

## First device execution — PASS, 2026-10-11 02:48 UTC (boot 13858eef, card 3)

Run in the owner-authorized window ("continue" after incident 5), concurrently
with two llama.cpp screens on cards 0-2, under `source /opt/intel/oneapi/setvars.sh`.
`validate.py --keep-build` regenerated and CPU-validated the fixtures and
rebuilt the binary (SHA256 03cec8dc…); `tests/device_window.py --authorized-device-window --card 3`
then ran **108 checks, all PASS** in 6.8 s: FP32 dequant bytes, FP32 GEMV
accumulator bytes and F16/BF16 output bytes identical to the shared CPU path for
real IQ2_S, IQ3_S and IQ4_NL blocks and synthetic F16/F32/IQ3_S/IQ4_NL
fixtures, at subgroup 16 and 32, with sign-mutated activations and changed
expert IDs/spans. Teardown complete (`safe_to_exit=true`, `in_flight=0`,
`live_bytes=0`), zero kernel fault-class lines during the test. Receipts:
[first-device-20261011/](first-device-20261011/). Performance was not measured
here; the next device step is the real-layer timing against the roofline table.
