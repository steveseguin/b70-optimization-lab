# Duration108 CPU guard and geometry prototype

The pilot is49 frames at640×384, original BF16 model and8+3 steps, using three
original fixtures. This prototype does not launch, load models, authorize the
new workload, prove its memory fit, qualify video quality or claim a speed gain.
The root-owned runtime integration supplies the same-size native oracle,
first-native memory/header barrier, worker admission and complete quality gates.
Historical sealed sources are unchanged.

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
The ordered22 registered rows have only `name`, `graph_sha256` and `role`:
12 required full outputs,8 required fill outputs and2 setup captures. The trusted
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
reservation evidence but writes nothing. The parent must bind actual22 capture
attempts/29 requests and maintain its normal durable4GiB storage ledger plus
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
14 full-size reservations +8 fill reservations =2,055,616,112 bytes
+1GiB cache +512MiB previews +192MiB logs =3,867,555,440 bytes <4GiB
```

Unexpected tensor shapes cannot consume the smaller fill allowance. The parent
still bounds other outputs/caches and rejects new work before reserve violation.
The first native output must verify source-derived51 audio latents and96480
waveform samples; they are not yet a measured49-frame result.

Run the synthetic/source controls with:

```bash
PYTHONDONTWRITEBYTECODE=1 python experiments/ltx25-b70/recovery/20261007-duration108-runtime/test_duration_guard.py
```
