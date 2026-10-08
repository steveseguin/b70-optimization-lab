# Packet 113 stream client contract

## What changed from packet 112 (read this first)

Packet 113 is packet 112 with three client-visible changes. Everything not listed
here is exactly as in 112: run names (`stream112-…`), node class names, the
qualification sequence and its graphs (same SHA-256 pins), qualification ids,
admission codes, the one-chain ordering rule, floors and latches.

1. **The receipt arrives before the MP4.** The server commits the chunk receipt as
   soon as the chunk's anchor (last decoded frame) is written and hashed. The
   preview MP4 is written afterwards by one in-order writer thread, which then
   commits a **preview record** `receipts/preview-<run_name>.json`, also served by
   `GET /ltx-stream/preview/<run_name>`. In the receipt, `preview.state` is
   `"queued"`, `preview.bytes` is `null` and `timing_ns.preview_written` is `null`.
   **Bounded wait rule (§6a):** after you have the receipt, submit the next chunk
   first, then wait at most 10 s for the preview record; use the MP4 only after the
   record exists and its `bytes`/`sha256` match the file.
2. **Chain reset (`reset: 1`).** A stream chunk may ask to restart the anchor chain
   (§1, §2). It is an unanchored text-to-video chunk in the stream_seq 0 form. It
   still takes the next `stream_seq`. The receipt says `anchored: false,
   reset: true`, delivers all frames (no leading frame to drop), and the chain
   continues from its anchor.
3. **New receipt fields:** `anchored`, `reset`, `reset_predecessor_anchor_sha256`,
   `anchor_diagnostics` (a border-vs-centre colour summary of the anchor frame,
   diagnostic only), `predecessor_preview`, `timing_ns.anchor_ready`,
   `timing_ns.preview_queued`, `timing_s.submit_to_anchor_ready`. Receipt schema
   `ltx.stream113.chunk-receipt.v1`, contract schema `ltx.stream113.chunk-contract.v3`.

Graphs without `reset` are byte-identical to packet 112 graphs, so a 112 graph
builder produces valid 113 requests. The 112 client needs `--packet 113` (see
`experiments/ltx25-b70/stream/CONTINUATION-CLIENT.md`). The flag selects the
sealed 113 module hashes and manifest and turns on the §6a wait rule. Without it
the client refuses the 113 server at preflight, because the manifest and module
hashes differ.

---

This is the request format for the packet 113 continuation stream server. It is
written for whoever builds the streaming client. The server listens on
`http://127.0.0.1:8188`. It is the ordinary ComfyUI `/prompt` endpoint, with an
admission layer in front of it and three extra routes.

The server accepts exactly one graph per parameter set. The reference builder
is `stream_contract.py`. It is stdlib-only, so import it rather than
hand-assembling JSON. The sealed copy is at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113/resolution/components/stream_contract.py`.

```python
import stream_contract as c
status = GET /ltx-stream/status     # gives frames, placement, next_stream_seq, chain.anchor_sha256, text_reuse
params = c.stream_params(status['frames'], stream_seq, prompt, seed, predecessor_anchor_sha256, scene_id,
                         reuse_text, placement=status['placement'], reset=0)   # reset=1: chain reset (113)
graph = c.build_chunk_graph(params)
```

The server rebuilds the graph from the parameters it parses out of yours and
compares the two as canonical JSON. Any extra node, missing node, changed input
or changed edge is refused before anything is queued.

## 1. The stream model: one anchor chain

- **Chunk `stream_seq = 0`** is the only unanchored request. It is plain
  text-to-video. It is the first chunk after the server's qualification, and
  there is exactly one per server launch. After a halt the server refuses
  everything, so the next unanchored chunk happens only on a new launch.
- **Chunk `stream_seq = n > 0`** is always conditioned on the last decoded frame
  of chunk `n-1`, at full F32 with no conversion. It goes through the native
  image-conditioning node at strength 1.0, before both samplers. The client
  never uploads pixels. It names the predecessor's anchor by its SHA-256 (taken
  from the predecessor's receipt), and the server loads the file itself.
- **Prompt modes.** Both modes use the same chain and the same request format:
  - *Continuous shot:* send the same `prompt` as chunk `n-1`.
  - *Cut:* send a different `prompt` at any chunk. The picture still flows
    through the cut, because chunk `n` is still conditioned on chunk `n-1`'s
    last frame. Where a "scene" ends is the client's decision.
  - `scene_id` (`[a-z0-9]{1,32}`) is only a label. It is echoed in the receipt
    and may change at any chunk. The server enforces nothing about it.
- **Chain reset (packet 113).** A chunk `stream_seq = n > 0` sent with
  `reset: 1` is **unanchored**. It is built exactly like chunk 0 (no anchor or
  conditioning nodes; `377.video_latent` is `["356", 0]` and `340.video_latent` is
  `["348", 0]`), with the extra input `"reset": 1` on `stream_output`. It still
  consumes the next `stream_seq`, the server's chain continues from **its** anchor,
  and chunk `n+1` must name the reset chunk's `anchor_out.sha256` as usual.
  - `predecessor_anchor_sha256` may be `""` or the current chain anchor (the
    previous chunk's `anchor_out.sha256`). It is recorded in the receipt as
    `reset_predecessor_anchor_sha256` and never consumed. Any other value is
    refused with `stale-anchor`, because it shows a client bug.
  - `reuse_text` must be `0`: a reset always encodes its prompt.
  - Use it to clear accumulated drift, such as the saturated border that frame
    anchoring builds up over many chunks. The cost is a visible discontinuity:
    the reset chunk's frame 0 does not continue the previous chunk.
  - The qualification's unanchored chunk 0 of each chain already covers this
    graph form. Resets add no graph signature.
- **Global order.** `stream_seq` must be exactly the server's
  `next_stream_seq`: 0, 1, 2, … with no gaps or repeats. Only one request may be
  queued or running at a time. Submit chunk `n+1` only after chunk `n`'s
  receipt exists, because you need its `anchor_out.sha256`.

## 2. Parameters of one chunk

| field | type | rule |
|---|---|---|
| `kind` | str | always `"stream"` (the `qualify-*` kinds belong to the server's own qualification run) |
| `frames` | int | must equal the server's `LTX_STREAM_FRAMES` (`49` by default, or `25`); see `GET /ltx-stream/status` → `frames` |
| `placement` | str | must equal the server's `LTX_SAMPLER_PLACEMENT` (`"two-way"` by default, or `"two-way20-28"`); see status → `placement` |
| `stream_seq` | int | `== next_stream_seq` |
| `chunk_index` | int | `== stream_seq` (`stream_params` sets it) |
| `prompt` | str | 1–4000 printable characters, no leading or trailing whitespace; it must also fit a qualified text window (§5) |
| `seed` | int | 0 … 2^64−1; used for both samplers (RandomNoise nodes 338 and 339) |
| `predecessor_anchor_sha256` | str | `""` for `stream_seq` 0; otherwise the `anchor_out.sha256` from the receipt of `stream_seq-1` |
| `scene_id` | str | `[a-z0-9]{1,32}`; label only |
| `reuse_text` | int | must be **exactly** `1` when the server has `text_reuse == 1`, `stream_seq > 0`, the chunk is not a reset and the prompt equals chunk `n-1`'s prompt. Otherwise it must be `0` (§5) |
| `reset` | int | packet 113: `0` (default; the key may be omitted in parameter dicts) or `1` for a chain reset (`stream_seq > 0` only). In the graph, `stream_output.inputs.reset` is present **only** when it is `1`; an explicit `"reset": 0` is not the contract form and is refused (`contract`) |

## 3. The HTTP request

```
POST /prompt
Content-Type: application/json
{"prompt": <graph>, "client_id": "<any non-empty string>", "prompt_id": "<uuid4, lowercase canonical>"}
```

- All three keys are required, and no other keys are accepted.
- `client_id` is required because ComfyUI only emits the per-node `executing`
  events the server uses for timing when a client id is present. Use the same id
  for the WebSocket.
- Generate `prompt_id` yourself. The receipt carries it.

### The graph for chunk n > 0 (frames 49, fresh text encode)

Node ids are fixed. The values that vary are noted after the example.

```json
{
  "338": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1001}},
  "339": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1001}},
  "340": {"class_type": "LTXVConcatAVLatent", "inputs": {"audio_latent": ["367", 1], "video_latent": ["stream_condition_b", 0]}},
  "341": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
  "344": {"class_type": "SamplerCustomAdvanced", "inputs": {"guider": ["388", 0], "latent_image": ["377", 0], "noise": ["339", 0], "sampler": ["352", 0], "sigmas": ["404", 0]}},
  "348": {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["367", 0], "upscale_model": ["420", 4], "vae": ["420", 2]}},
  "352": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
  "356": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"batch_size": 1, "height": 128, "length": 49, "width": 128}},
  "358": {"class_type": "LTXVAudioVAEDecode", "inputs": {"audio_vae": ["420", 3], "samples": ["369", 1]}},
  "364": {"class_type": "LTXPipelineTextEncode", "inputs": {"clip": ["420", 1], "clip_index": 11201001, "comparison_mode": "stream-candidate-112-v1", "depth": 2, "mode": "pipeline-window", "output_size": "256x256", "qualification_id": "09c1fda000494fb391e934fcffc83aa5169d80626a13f3c9edf715111da318b8", "run_name": "stream112-s00000001", "speed_only": false, "text": "A small red wooden toy boat drifts on calm water at sunset."}},
  "365": {"class_type": "LTXVConditioning", "inputs": {"frame_rate": 24.0, "negative": ["stream_text", 0], "positive": ["stream_text", 0]}},
  "366": {"class_type": "LTXVEmptyLatentAudio", "inputs": {"audio_vae": ["420", 3], "batch_size": 1, "frame_rate": 24.0, "frames_number": 49}},
  "367": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["344", 0]}},
  "368": {"class_type": "SamplerCustomAdvanced", "inputs": {"guider": ["391", 0], "latent_image": ["340", 0], "noise": ["338", 0], "sampler": ["341", 0], "sigmas": ["395", 0]}},
  "369": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["368", 0]}},
  "374": {"class_type": "VAEDecode", "inputs": {"samples": ["369", 0], "vae": ["420", 2]}},
  "377": {"class_type": "LTXVConcatAVLatent", "inputs": {"audio_latent": ["366", 0], "video_latent": ["stream_condition_a", 0]}},
  "388": {"class_type": "LTXVDualCFGGuider", "inputs": {"audio_cfg": 1.0, "model": ["420", 0], "negative": ["365", 1], "positive": ["365", 0], "video_cfg": 1.0}},
  "391": {"class_type": "LTXVDualCFGGuider", "inputs": {"audio_cfg": 1.0, "model": ["420", 0], "negative": ["365", 1], "positive": ["365", 0], "video_cfg": 1.0}},
  "395": {"class_type": "ManualSigmas", "inputs": {"sigmas": "0.85, 0.7250, 0.4219, 0.0"}},
  "404": {"class_type": "ManualSigmas", "inputs": {"sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"}},
  "420": {"class_type": "LTXHostEmbeddingComponents", "inputs": {"encoder_mode": "control", "placement": "split"}},
  "stream_anchor": {"class_type": "LTXStreamAnchor112", "inputs": {"predecessor_anchor_sha256": "ffff…(64 hex)", "run_name": "stream112-s00000001"}},
  "stream_condition_a": {"class_type": "LTXStreamCondition112", "inputs": {"bypass": false, "image": ["stream_anchor", 0], "latent": ["356", 0], "run_name": "stream112-s00000001", "stage": "A", "strength": 1.0, "vae": ["420", 2]}},
  "stream_condition_b": {"class_type": "LTXStreamCondition112", "inputs": {"bypass": false, "image": ["stream_anchor", 0], "latent": ["348", 0], "run_name": "stream112-s00000001", "stage": "B", "strength": 1.0, "vae": ["420", 2]}},
  "stream_output": {"class_type": "LTXStreamChunk112", "inputs": {"audio": ["358", 0], "audio_latent": ["369", 1], "chunk_index": 1, "frames": 49, "images": ["374", 0], "kind": "stream", "placement": "two-way", "predecessor_anchor_sha256": "ffff…(64 hex)", "reuse_text": 0, "run_name": "stream112-s00000001", "scene_id": "boat", "seed": 1001, "stream_seq": 1, "video_latent": ["369", 0]}},
  "stream_text": {"class_type": "LTXStreamText112", "inputs": {"conditioning": ["364", 0], "run_name": "stream112-s00000001", "text": "A small red wooden toy boat drifts on calm water at sunset."}}
}
```

Values that vary per chunk:

- `run_name` is `stream112-s%08d` of `stream_seq`. It appears identically on
  `364`, `stream_text`, `stream_anchor`, both `stream_condition_*` and
  `stream_output`.
- `338/339.noise_seed` is `seed`.
- `364.clip_index` is `11201000 + stream_seq`.
- `364.text` and `stream_text.text` are both the prompt.
- `364.qualification_id` depends on `frames` and `placement`:
  - 49 frames, `two-way` → `09c1fda000494fb391e934fcffc83aa5169d80626a13f3c9edf715111da318b8`
  - 49 frames, `two-way20-28` → `0f7cda48784e92bdb6ff99708ae12809838eaf0b1db535d259f0a116a2ab9b0e`
  - 25 frames, `two-way` → `b5ea97da305a36b13922d78d8fb4f5b6353ab71ad5e9680ad8bf81ce60c4a2b3`
  - 25 frames, `two-way20-28` → `7d40ff29e6d76a9b5bfc5503933d1d4e95d6e36532a51d8e76a2bd3a5e5f01ad`

  The status route also returns it.
- `356.length`, `366.frames_number` and `stream_output.frames` are all `frames`.
- `stream_output.placement` is the server placement.
- `stream_output` also carries `scene_id`, `seed`, `stream_seq`, `chunk_index`,
  `predecessor_anchor_sha256` and `reuse_text`.
- `stream_anchor.predecessor_anchor_sha256` is the same hash as in `stream_output`.
- A reset chunk adds `"reset": 1` to `stream_output.inputs` and has no
  `stream_anchor` or `stream_condition_*` nodes.

The other two shapes differ from this example as follows:

- **Chunk 0 and reset chunks:** there is no `stream_anchor`, `stream_condition_a` or
  `stream_condition_b`. Node `377.video_latent` is `["356", 0]` and
  `340.video_latent` is `["348", 0]`. `predecessor_anchor_sha256` is `""`.
- **Text reuse (`reuse_text: 1`):** node `364` is absent, and `stream_text` has
  no `conditioning` input (only `run_name` and `text`).

Neither `LTXGraphCaptureGate` nor `LTXTextEncoderGraphGate` appears in stream
graphs. The graph routes and text graphs installed during qualification stay
installed on the resident model, so those gates would only re-run checks and
write about 0.4 MB of report files per chunk. Every chunk's route inventory is
still checked before and after it runs (§7). The last qualification chain uses
exactly this gate-less form.

## 4. Admission responses

The admission layer answers before ComfyUI validates or queues anything:

- **HTTP 200:** ComfyUI's normal `{"prompt_id": …, "number": …}`. The chunk is
  queued.
- **HTTP 400:** malformed body. The `code` is `contract`, `missing-client-id`
  or `missing-prompt-id`.
- **HTTP 409:** the request is refused and **nothing is latched**. Fix the
  request and resubmit. The body is `{"error": {"code": …, "message": …}}`:
  - `busy`: a request is still queued or running, or an action is active.
    Resubmit after the previous receipt exists.
  - `order`: the request is not the expected next `stream_seq`, or it is a
    chain restart.
  - `stale-anchor`: `predecessor_anchor_sha256` is not the anchor of `stream_seq-1`
    (for a reset: neither `""` nor that anchor).
  - `contract`: the graph differs from `build_chunk_graph(params)`, or
    `frames` is wrong.
  - `text-reuse-rule`: `reuse_text` does not match §2.
  - `text-cache-missing`: no cached encode exists for a reuse request.
  - `window-not-captured`, `window-not-qualified`: see §5.
  - `not-streaming`: qualification has not passed yet.
  - `not-prepared`, `storage`, `precheck-error`.
- **HTTP 503 `halted`:** the server is latched. See §8.

## 5. Text handling

- **Default `LTX_STREAM_TEXT_REUSE=0`:** every chunk re-encodes its prompt, so
  `reuse_text` is always 0.
- **`LTX_STREAM_TEXT_REUSE=1`** (an owner decision): when the prompt equals the
  previous chunk's prompt, the client *must* send `reuse_text: 1`. The server
  then serves a copy of its single cached encode, which is the chain's latest
  fresh encode of that prompt. On a cut, send `reuse_text: 0`; the new prompt is
  encoded and becomes the cache.
- **Text window rule.** The encoder pads to the smallest captured window bucket
  (64/128/256/512 rows) that holds the prompt. The transformer's per-block
  graphs are frozen after qualification. A prompt whose bucket differs from the
  qualification prompts' bucket (64 rows, roughly up to 60 Gemma tokens) is
  refused with `window-not-qualified`. That refusal is not latched. Without this
  check, a different bucket would hit an unseen graph signature and latch the
  server. `GET /ltx-stream/status` → `qualified_text_windows` gives the set.
  Keep prompts short.

## 6. Completion, the receipt and the preview record

- **Completion signal:** ComfyUI's WebSocket `ws://127.0.0.1:8188/ws?clientId=<client_id>`
  sends `{"type": "execution_success", "data": {"prompt_id": …}}` once the
  receipt has been committed. If you do not use the WebSocket, poll
  `GET /ltx-stream/receipt/<run_name>`: it returns 404 until the receipt is
  committed, then the receipt JSON. An `execution_error` for your `prompt_id`
  means the server has halted.
- **Receipt file:** `<server run dir>/receipts/receipt-<run_name>.json`. The
  server run dir is
  `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-113-<placement>-w1-b1-p1-dxpu2-s256x256-f<frames>`.
  For the planned launch that is `…-113-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49`.
  The status route gives `receipt_dir`. The receipt is written once (exclusive
  create plus fsync), only after all checks pass, and **at anchor ready**, before
  the MP4 exists. Schema `ltx.stream113.chunk-receipt.v1`.

Receipt fields:

| field | meaning |
|---|---|
| `run_name`, `prompt_id`, `kind`, `stream_seq`, `chunk_index`, `scene_id`, `seed`, `frames`, `placement` | identity |
| `prompt_sha256`, `prompt_changed` (`null` for chunk 0), `reuse_text`, `server_text_reuse` | text |
| `text.reused`, `text.tensors[]` | SHA-256 of every conditioning tensor actually fed to the samplers |
| `tensors.{images,video_latent,audio_latent,waveform}` | `shape`, `dtype` (`torch.float32`), `finite: true`, and `sha256` of the complete little-endian F32 payload |
| `anchored`, `reset`, `reset_predecessor_anchor_sha256` | `anchored` is `false` for chunk 0 and for resets. `reset` is `true` only for a chain reset. The last field is the hash the reset named (`""` allowed), or `null` |
| `anchor_in` | `null` when `anchored` is false; otherwise `{sha256, path, source_run_name}` |
| `anchor_out` | `{sha256, path, bytes: 786432, frame_index: frames-1, shape: [1,256,256,3], dtype: "F32"}`. **Send this `sha256` as the next chunk's `predecessor_anchor_sha256`.** |
| `delivery` | `{frames_total, fps: 24, new_frames, first_new_frame_index, drop_leading_frames}`. Unanchored chunks (chunk 0, resets) deliver all frames. Every anchored chunk's frame 0 re-renders the predecessor's last frame, so **drop 1 leading frame**: 48 new frames at 49 (2.0 s), 24 new frames at 25 (1.0 s). |
| `preview` | `{path (absolute .mp4, final name), relative_to_output_directory, state: "queued", bytes: null, record (absolute path of the preview record), container: "mp4", lossy: true, fps: 24, frames, includes_overlap_frame, queue_depth_at_submit, submit_blocked_s}` |
| `predecessor_preview` | the previous chunk's preview record summary `{run_name, preview_written_ns, bytes, sha256, timing_s}` if it was written by the time this receipt was staged, else `null` |
| `anchor_diagnostics` | diagnostic only, never used by the server. It summarises the anchor frame (the F32 values): `border_px: 16`; the outer 16-pixel ring vs the middle half square; for each region `*_mean_chroma` (mean of max(rgb)−min(rgb)), `*_mean_luma` (Rec.709 weights), `*_clipped_fraction` (any channel ≥0.999 or ≤0.001) and `*_pixels`; plus `border_to_centre_chroma_ratio` (`null` if the centre chroma is 0). A rising ratio over a stream is the saturated-border drift |
| `timing_ns` | wall-clock ns: `submit` (admission accepted), `execution_start`, `sampler_a_start` (node 344 starts), `sampler_b_start` (368), `decode_start` (374), `decode_done` (output node starts, so both decoders are finished), **`anchor_ready`** (anchor fsynced, tensors hashed), `preview_queued` (handed to the writer, after any back-pressure wait), `preview_written` (**always `null` here**; see the preview record), `receipt_staged` |
| `timing_s` | `submit_to_sampler_start`, `submit_to_decode_done`, **`submit_to_anchor_ready`** (the chain's per-chunk lag in 113), `anchor_ready_to_receipt_staged`; `submit_to_preview_written` and `execution_start_to_preview_written` are `null` (in the preview record instead) |
| `graph` | `routes` (48), `signatures_per_route`, `new_captures` (0 in streaming), `captures_frozen: true` |
| `memory` | free bytes and peaks per card before and after the chunk, and per conditioning stage |
| `storage` | `free_bytes`, `consumed_bytes`, `allowance_bytes` (3 GiB), `reserve_bytes` (50 GiB) |
| `sanity` | always `{finite, shapes, anchor_chain}` all true. A failing check halts instead of writing a receipt. |
| `committed: true`, `commit_ns`, `plan_sha256`, `qualification_id`, `qualification_verdict_sha256`, `server_identity_sha256`, `runtime_manifest_sha256` | provenance |

**The preview MP4.** `preview.path` is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/output/<run_name>/preview_00001_.mp4`.
The server fixes the counter suffix when it stages the receipt, using ComfyUI's own
rule, so always take the path from the receipt. It is the lossy CreateVideo +
SaveVideo output (8-bit sRGB, mp4 auto codec, 24 fps; the same calls and arguments
as 112's writer), with the chunk's own audio. For continuous playback, drop the
first video frame of every anchored chunk. Do not drop it for chunk 0 or a reset.

### 6a. The preview record and the bounded wait rule (packet 113)

- The writer encodes the MP4 under a hidden temporary name
  (`.preview_00001_.mp4.partial`), fsyncs it, and hard-links it to the final name.
  A file at the final name is therefore always complete.
- Then it commits `receipts/preview-<run_name>.json`, schema
  `ltx.stream113.preview-record.v1`: `run_name`, `prompt_id`, `path`,
  `relative_to_output_directory`, `bytes`, `sha256` (of the MP4),
  `timing_ns {submit, anchor_ready, preview_queued, write_start, preview_written}`,
  and `timing_s {submit_to_preview_written, anchor_ready_to_preview_written,
  queue_wait, write}`. `GET /ltx-stream/preview/<run_name>` returns it.
  `stream_receipts.validate_preview_record(record, receipt)` checks it and its
  binding to the receipt.
- One writer, FIFO: previews are written in `stream_seq` order. The queue holds
  two waiting previews. A full queue makes the next chunk's output node wait
  (back-pressure), so no preview is ever dropped.
- **Wait rule.** After the receipt of chunk `n` exists:
  1. Submit chunk `n+1` (you only need `anchor_out.sha256`).
  2. Poll `GET /ltx-stream/preview/<run_name of n>`. It returns 404 until the
     record is committed.
  3. **Give up after 10 s** (the client's `--save-wait`). A healthy writer needs
     about 0.2–0.3 s, plus at most two queued previews ahead of it. If the
     server is halted, the route returns 503 `halted`: stop. If the record has
     not appeared and the server is not halted, stop and report (client exit 7).
     Do not resubmit.
  4. Use the MP4 only once the record exists and the file's size and SHA-256
     equal the record's.
- A preview write failure latches the server like any other fault. It writes
  `stream-preview-failure-<run_name>.json`, sets `halted`, and later posts get
  503. Previews still queued after a failure are not written.
- If the server is stopped (SIGINT) while a preview is queued or being written,
  that chunk may be left without a record (and with a `.partial` file). Its receipt
  and anchor are still valid.

**Audio.** At 49 frames each chunk has 96,480 samples (2.01 s) against 2.04 s
of video. At 25 frames it is 48,480 samples (1.01 s) against 1.04 s. No trim or
alignment rule is defined, so concatenating chunk audio is not lossless or
aligned. The owner has not decided this yet.

## 7. Other routes

- `GET /ltx-stream/status` returns:
  - `phase` (`stream_setup` | `stream_qualification` | `stream`), `halted`
    (reason or `null`), `fault`, `active`
  - `next_stream_seq`, `stream_completed`, `frames`, `placement`, `text_reuse`, `qualification_id`
  - `chain` (`{last_stream_seq, last_run_name, anchor_sha256, prompt_sha256}`
    or `null`), `last_stream_receipts`
  - `qualified_text_windows`, `storage`, `receipt_dir`, `output_directory`

  It answers 409 `busy` while the qualification verdict action runs. A client
  can resume after its own crash by reading `chain.anchor_sha256` and
  `next_stream_seq`.
- `GET /ltx-stream/receipt/<run_name>` returns the committed receipt, or 404.
- `GET /ltx-stream/preview/<run_name>` (113) returns the committed preview record,
  404 if it is not written yet, or 503 `halted` after a preview failure.
- 113 status additions: `packet: 113`,
  `features: {async_preview, chain_reset, anchor_diagnostics}` (all true),
  `preview_writer: {submitted, completed, pending, failed, skipped_after_failure, maxsize}`.
- `POST /ltx-stream/action {"action": "qualify-verdict"}` is used only by the
  qualification driver. It runs once.

## 8. Halts, bounds and what the client must not do

- Any exception inside an admitted chunk latches the server. Causes include a
  memory floor, a route or signature change, nonfinite output, a preview write
  failure, a storage limit or a device fault. After a latch, every later POST
  gets 503 `halted`. The server process stays up for inspection, and nothing is
  retried or restarted. The client must stop and report. It must not resubmit
  in a loop, and it must never signal or restart the server.
- **Storage:** the stream may consume at most 3 GiB net (measured as the drop in
  free space since launch) while keeping 50 GiB free. That covers previews,
  anchors, receipts and per-chunk text-node receipts. The server keeps the two
  newest anchor files and deletes older ones. The client may delete preview MP4s
  it has consumed, and doing so returns their space to the allowance. It must
  not touch anything else in the run or output directories (including `.partial`
  files and preview records).
- The client never uploads images, anchors or tensors, and never names a server
  path in a request.
