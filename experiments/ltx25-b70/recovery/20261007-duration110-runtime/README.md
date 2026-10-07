# Duration110 full ten-fixture49-frame qualification runtime

CPU-only successor author sources. No packet build or GPU execution is authorized
by this README. The unchanged109 numerical path uses49 frames at640×384,
BF16,8+3 sampling steps, named20/28 ownership and W2/B1/shared pool1. This
successor expands the original fixture coverage to all ten, with20 native
requests (two independent passes),14 candidate requests and14 timed requests.
Nine setup requests give57 attempts and50 captures. Each optimized block has
four fills and ten scored outputs; only the timed block yields nine intervals.

The constructor remains qualified99b, placement source remains the four exact
100b files, and predecessor is109, manifest
`e91e8994642cf03210c5bde724a485e0c314a409a300a40379cc79a43fc67906`.
Preserve8/8/2/9GiB native admission, the first-native shape/finite/memory barrier,
all four exact tensor comparisons, failure evidence and healthy-app retention.
No automatic retry or restart. Passing this suite establishes scoped exact
qualification; it does not establish adoption, a speed gain, visual judgement,
endurance or a public record.

Build admission requires50GiB reserve +9GiB run allowance +384MiB source
allowance before destination creation. Startup explicitly overrides the inherited
4GiB allowance with9GiB, while request and server ledgers retain50GiB reserve.

## Geometry transformation

`duration_guard.transform_geometry(raw)` accepts only pristine qualified99b
`source/scripts/ltx_output_size_98.py`, SHA256
`895b1c02ac764838b5d69446b0e5cf054884b191dd8b9446c5ce641ec40f2e52`.
Apply it before appending the parent's new phase-authorization extension.
It requires explicit640×384 server configuration and changes video temporal
latent4→7, images25→49, audio latent26→51 and waveform48480→96480.
Video tokens are420/1680. Seeded decoder probe rows gain `frame_count:49` and
`audio_latent_shape:[1,8,51,16]`; their original ten-seed count is unchanged.
Historical25-frame reference lookup is refused. The parent must separately
update graph inputs, admission gates, qualification identity and reference file caps.

## Before-write capture guard

The frozen capture writer has SHA256
`6495b0c4de7ac054e35a39fb00e7c7b979d5fb51d6e77bc0dee18bad9d0ec9da`.
`transform_capture(path,raw)` supports all three pinned copies:

- `capture_node.py`
- `source/scripts/capture_node.py`
- `source/custom_nodes/ltx_baseline_capture/__init__.py`

It retains the existing detach/CPU/contiguous handling, tensor hashes, finiteness
checks and min/max/std computations without adding tensor arithmetic. The only
filesystem reordering moves `out.mkdir` after those original statistics and the
new `ltx_duration_guard.require_capture_prewrite(tensors,report,run_name)` hook.
Rejected shape/dtype/nonfinite/identity/budget data therefore opens no capture
output file and creates no capture output directory. Failed tensor payloads are
not written; existing request/fault receipts must preserve the refusal reason.

Configure once with `configure(plan_sha256,capture_rows,active_request)`.
The ordered50 registered rows have only `name`, `graph_sha256` and `role`:
40 required full outputs,8 required fill outputs and2 setup captures. The trusted
parent derives these rows from its immutable approved plan/schedule. The callback
must obtain the actual session's active `name`, `prompt_id`, `plan_sha256` and
registered `graph_sha256` under the authority lock. Caller labels or filenames
alone cannot authorize a role. The callback is checked twice before committing
the reservation. Parent session request/phase, exact-graph and source guards
remain mandatory; this helper is not their replacement.

Full output requires these exact four contiguous dense **CPU float32** tensors:

| Key | Shape |
| --- | --- |
| images | `[49,384,640,3]` |
| video_latent | `[1,128,7,12,20]` |
| audio_latent | `[1,8,51,16]` |
| waveform | `[1,2,96480]` |

A fill requires images`[1,8,8,3]`, waveform`[1,2,8]`, the same audio latent and
video latent either stageA`[1,128,7,6,10]` or stageB as above. Whole tuples are
checked; mixed full-image/placeholder-waveform outputs are rejected. Setup
captures accept only one of those complete full/fill tuples and are always
charged as full. Sample rate must be48000; existing report shapes/dtypes/hashes,
strict true finiteness and finite scalar statistics must match tensor metadata.
No conversion, tensor scan or GPU operation is performed by the guard.

Reservations occur before mkdir/save and cannot be refunded/retried. Any guard
failure latches rejection for future capture writes. `receipt()` exposes bounded
reservation evidence but writes nothing. The parent must bind actual50 capture
attempts/57 requests and maintain its normal durable9GiB storage ledger plus
50GiB remaining-space admission; this helper bounds raw captures only.

## Byte accounting and serializer binding

The source-pinned writer calls `safetensors.torch.save_file(tensors,path)` with
no user metadata. The installed wrapper passes exactly dtype, shape, data pointer
and data length to the Rust writer. `serializer_binding(sources)` verifies both:

- `torch.py`: `f3f476d1f8c04fe65fa3797426556a0b7afa43f8c4db9db6b799c7cf84748f3d`
- `_safetensors_rust.abi3.so`: `e6f17a9e9846bc2bc4ad94cc5431746b59785de3d2681ef2666e8890ae192dfb`

The parent must include those installed files in runtime identity and preserve
their integrity checks. A different writer or added user metadata requires a new
bound. Safetensors uses an8-byte length followed by JSON padded to8 bytes. With
these four fixed names/F32/shapes/offsets, conservative JSON accounting is below
1KiB; the reservation nevertheless allows65536 JSON bytes plus the8-byte prefix.
The CPU test also exercises the actual pinned Rust serializer on four4-byte
buffers without importing Torch or writing a file.

Full payload146,164,992 bytes plus65,544 header bytes gives146,230,536 bytes.
The largest fill, including stageB latents and the same header allowance, is
952,648 bytes, below its enforced1MiB cap. Thus:

```text
42 full-size reservations +8 fill reservations =6,150,071,120 bytes
+1GiB cache +512MiB previews +192MiB logs =7,962,010,448 bytes <9GiB
```

Unexpected tensor shapes cannot consume the smaller fill allowance. The parent
still bounds other outputs/caches and rejects new work before reserve violation.
The first native output must verify source-derived51 audio latents and96480
waveform samples; every output still requires its own exact reference comparison.

Run the synthetic/source controls with:

```bash
PYTHONDONTWRITEBYTECODE=1 python experiments/ltx25-b70/recovery/20261007-duration110-runtime/test_duration_guard.py
```
