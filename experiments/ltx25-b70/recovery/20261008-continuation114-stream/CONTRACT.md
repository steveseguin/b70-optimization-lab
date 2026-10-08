# Packet 114 stream client contract

## What changed from packet 113 (read this first)

Packet 114 keeps 113's request model: one anchor chain, one request at a time,
strict `stream_seq` order, the predecessor named by its anchor hash, chain resets,
the admission codes, the floors and the latches. What changes for a client:

1. **The anchor is chosen at launch (`LTX_ANCHOR`).**
   - `latent` (default, new): chunk `n` is conditioned on two latent slices of
     chunk `n-1`: the last latent slot of its stage-A output (node 367, before the
     upsampler) for stage A, and the last latent slot of its stage-B output
     (node 369) for stage B. The server copies each slice into slot 0 of the
     stage's latent and sets that slot's mask to 0. That is exactly what the
     native image-conditioning node does after its VAE encode
     (`comfy_extras/nodes_lt.py:156,172-175`), without the encode. **This changes
     the output** compared with 113.
   - `frame`: 113's decoded-last-frame anchor through the native
     image-conditioning node, kept so an A/B exists.

   Either way the client still sends the predecessor's `anchor_out.sha256` as
   `predecessor_anchor_sha256`, and never uploads anything. With `latent` that
   hash names a 40,960-byte file instead of a 786,432-byte frame.
2. **The decode is off the graph.** The graph has no decoder nodes. The output
   node takes the three latents and the two resident VAEs and hands the decode to
   one in-order decode thread on xpu:3. With `latent` the receipt is committed
   when the latents are hashed and the latent anchor is durable (`anchor_ready`),
   **before** the decode. The decode thread then commits a **decode record**
   (`receipts/decode-<run_name>.json`, also `GET /ltx-stream/decode/<run_name>`)
   with the decoded image and waveform hashes, and only then is the MP4 written
   and its preview record committed. With `frame` the chain waits for its own
   decode (the anchor is the decoded frame), so the decode record exists before
   the receipt.
3. **Chunk length at launch (`LTX_STREAM_FRAMES` = `49` or `97`).** At 97 frames
   an anchored chunk delivers 96 new frames (4.0 s); chunk 0 and resets deliver 97.
   25 frames is no longer offered.
4. **Text reuse is on by default (`LTX_STREAM_TEXT_REUSE=1`).** When the prompt
   equals the previous chunk's prompt, the client **must** send `reuse_text: 1`
   (§5). `0` still works as a launch option.
5. **New names.** Every run name starts with `stream114-`
   (`stream114-s%08d`, `stream114-q{eager,graph,repeat}-c00000{0,1,2}`, setup
   `stream114-window-probe` and `stream114-prepare`). The node classes are
   `…114`. Graphs, qualification graphs, qualification ids and the plan are all
   new, so a 113 graph builder does not produce valid 114 requests.
6. **New parameter `anchor`** in every parameter set and on the output node; it
   must equal the server's `LTX_ANCHOR` (status → `anchor`).
7. **Receipts.** Schema `ltx.stream114.chunk-receipt.v1`. `tensors` holds the three
   latents only (`video_latent`, `audio_latent`, `stage_a_latent`). The decoded
   image and waveform hashes, the border diagnostic and the qualification capture
   moved to the decode record. New: `anchor`, `slot0_pin` (diagnostic), `decode`,
   `predecessor_decode`, `decode_at_start`, a node-by-node `timing_ns`, and
   `timing_s.sampler_a_split`.
8. **Client:** `ltx_continuation_client.py --packet 114`.

---

This is the request format for the packet 114 continuation stream server. It is
written for whoever builds the streaming client. The server listens on
`http://127.0.0.1:8188`. It is the ordinary ComfyUI `/prompt` endpoint, with an
admission layer in front of it and five extra routes.

The server accepts exactly one graph per parameter set. The reference builder is
`stream_contract.py`. It is stdlib-only, so import it rather than
hand-assembling JSON. The sealed copy is at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-114/resolution/components/stream_contract.py`.

```python
import stream_contract as c
status = GET /ltx-stream/status     # frames, placement, anchor, next_stream_seq, chain.anchor_sha256, text_reuse
params = c.stream_params(status['frames'], stream_seq, prompt, seed, predecessor_anchor_sha256, scene_id,
                         reuse_text, placement=status['placement'], reset=0, anchor=status['anchor'])
graph = c.build_chunk_graph(params)
```

The server rebuilds the graph from the parameters it parses out of yours and
compares the two as canonical JSON. Any extra node, missing node, changed input
or changed edge is refused before anything is queued.

## 1. The stream model: one anchor chain

- **Chunk `stream_seq = 0`** is unanchored text-to-video. It is the first chunk
  after the server's qualification, and there is exactly one per launch. After a
  halt the server refuses everything.
- **Chunk `stream_seq = n > 0`** is conditioned on chunk `n-1`, at full F32 with no
  conversion, at strength 1.0, before both samplers:
  - `latent`: stage A gets chunk `n-1`'s stage-A slot `T-1`, stage B gets its
    stage-B slot `T-1` (`T` = 7 latent frames at 49, 13 at 97). Stage B is
    re-pinned after the upsampler, which drops the mask, exactly as 113 does.
  - `frame`: both stages get chunk `n-1`'s decoded last frame through
    `LTXVImgToVideoInplace` (113).

  The client names the predecessor's anchor by its SHA-256 (from the predecessor's
  receipt); the server loads and re-verifies the file itself.
- **Prompt modes.** *Continuous shot:* send the same prompt as chunk `n-1` (with
  `reuse_text: 1` on a reuse server). *Cut:* send a different prompt at any chunk;
  the picture still flows through the cut. `scene_id` (`[a-z0-9]{1,32}`) is only a
  label.
- **Chain reset (`reset: 1`, from 113).** A chunk `stream_seq = n > 0` sent with
  `reset: 1` is unanchored, built exactly like chunk 0 plus `"reset": 1` on
  `stream_output`. It takes the next `stream_seq`, the chain continues from **its**
  anchor, and chunk `n+1` names the reset chunk's `anchor_out.sha256`.
  `predecessor_anchor_sha256` may be `""` or the current chain anchor (recorded as
  `reset_predecessor_anchor_sha256`, never consumed); anything else is
  `stale-anchor`. `reuse_text` must be `0`. The qualification's chunk 0 of each
  chain already covers this graph form.
- **Global order.** `stream_seq` must be exactly the server's `next_stream_seq`.
  Only one request may be queued or running at a time. Submit chunk `n+1` only
  after chunk `n`'s receipt exists.

## 2. Parameters of one chunk

| field | type | rule |
|---|---|---|
| `kind` | str | always `"stream"` (the `qualify-*` kinds belong to the server's own qualification run) |
| `frames` | int | must equal the server's `LTX_STREAM_FRAMES` (`49` or `97`); status → `frames` |
| `placement` | str | must equal the server's `LTX_SAMPLER_PLACEMENT` (`"two-way"` or `"two-way20-28"`); status → `placement` |
| `anchor` | str | **114:** must equal the server's `LTX_ANCHOR` (`"latent"` or `"frame"`); status → `anchor` |
| `stream_seq` | int | `== next_stream_seq` |
| `chunk_index` | int | `== stream_seq` (`stream_params` sets it) |
| `prompt` | str | 1–4000 printable characters, no leading or trailing whitespace; it must also fit a qualified text window (§5) |
| `seed` | int | 0 … 2^64−1; used for both samplers (RandomNoise nodes 338 and 339) |
| `predecessor_anchor_sha256` | str | `""` for `stream_seq` 0; otherwise the `anchor_out.sha256` from the receipt of `stream_seq-1` |
| `scene_id` | str | `[a-z0-9]{1,32}`; label only |
| `reuse_text` | int | must be **exactly** `1` when the server has `text_reuse == 1`, `stream_seq > 0`, the chunk is not a reset and the prompt equals chunk `n-1`'s prompt; otherwise `0` (§5) |
| `reset` | int | `0` (default; may be omitted in parameter dicts) or `1` for a chain reset (`stream_seq > 0` only). In the graph, `stream_output.inputs.reset` is present **only** when it is `1` |

## 3. The HTTP request

```
POST /prompt
Content-Type: application/json
{"prompt": <graph>, "client_id": "<any non-empty string>", "prompt_id": "<uuid4, lowercase canonical>"}
```

All three keys are required and no other keys are accepted. `client_id` is
required because ComfyUI only emits the per-node `executing` events the server
uses for timing when a client id is present.

### The graph for chunk n > 0 (97 frames, latent anchor, fresh text encode)

```json
{
  "338": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1001}},
  "339": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1001}},
  "340": {"class_type": "LTXVConcatAVLatent", "inputs": {"audio_latent": ["367", 1], "video_latent": ["stream_condition_b", 0]}},
  "341": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
  "344": {"class_type": "SamplerCustomAdvanced", "inputs": {"guider": ["388", 0], "latent_image": ["377", 0], "noise": ["339", 0], "sampler": ["352", 0], "sigmas": ["404", 0]}},
  "348": {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["367", 0], "upscale_model": ["420", 4], "vae": ["420", 2]}},
  "352": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler_ancestral"}},
  "356": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"batch_size": 1, "height": 128, "length": 97, "width": 128}},
  "364": {"class_type": "LTXPipelineTextEncode", "inputs": {"clip": ["420", 1], "clip_index": 11401001, "comparison_mode": "stream-candidate-114-v1", "depth": 2, "mode": "pipeline-window", "output_size": "256x256", "qualification_id": "d85b23d7…3d52", "run_name": "stream114-s00000001", "speed_only": false, "text": "A small red wooden toy boat drifts on calm water at sunset."}},
  "365": {"class_type": "LTXVConditioning", "inputs": {"frame_rate": 24.0, "negative": ["stream_text", 0], "positive": ["stream_text", 0]}},
  "366": {"class_type": "LTXVEmptyLatentAudio", "inputs": {"audio_vae": ["420", 3], "batch_size": 1, "frame_rate": 24.0, "frames_number": 97}},
  "367": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["344", 0]}},
  "368": {"class_type": "SamplerCustomAdvanced", "inputs": {"guider": ["391", 0], "latent_image": ["340", 0], "noise": ["338", 0], "sampler": ["341", 0], "sigmas": ["395", 0]}},
  "369": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["368", 0]}},
  "377": {"class_type": "LTXVConcatAVLatent", "inputs": {"audio_latent": ["366", 0], "video_latent": ["stream_condition_a", 0]}},
  "388": {"class_type": "LTXVDualCFGGuider", "inputs": {"audio_cfg": 1.0, "model": ["420", 0], "negative": ["365", 1], "positive": ["365", 0], "video_cfg": 1.0}},
  "391": {"class_type": "LTXVDualCFGGuider", "inputs": {"audio_cfg": 1.0, "model": ["420", 0], "negative": ["365", 1], "positive": ["365", 0], "video_cfg": 1.0}},
  "395": {"class_type": "ManualSigmas", "inputs": {"sigmas": "0.85, 0.7250, 0.4219, 0.0"}},
  "404": {"class_type": "ManualSigmas", "inputs": {"sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"}},
  "420": {"class_type": "LTXHostEmbeddingComponents", "inputs": {"encoder_mode": "control", "placement": "split"}},
  "stream_anchor": {"class_type": "LTXStreamLatentAnchor114", "inputs": {"predecessor_anchor_sha256": "ffff…(64 hex)", "run_name": "stream114-s00000001"}},
  "stream_condition_a": {"class_type": "LTXStreamLatentCondition114", "inputs": {"anchor": ["stream_anchor", 0], "latent": ["356", 0], "run_name": "stream114-s00000001", "stage": "A", "strength": 1.0}},
  "stream_condition_b": {"class_type": "LTXStreamLatentCondition114", "inputs": {"anchor": ["stream_anchor", 1], "latent": ["348", 0], "run_name": "stream114-s00000001", "stage": "B", "strength": 1.0}},
  "stream_output": {"class_type": "LTXStreamChunk114", "inputs": {"anchor": "latent", "audio_latent": ["369", 1], "audio_vae": ["420", 3], "chunk_index": 1, "frames": 97, "kind": "stream", "placement": "two-way20-28", "predecessor_anchor_sha256": "ffff…(64 hex)", "reuse_text": 0, "run_name": "stream114-s00000001", "scene_id": "boat", "seed": 1001, "stage_a_latent": ["367", 0], "stream_seq": 1, "vae": ["420", 2], "video_latent": ["369", 0]}},
  "stream_text": {"class_type": "LTXStreamText114", "inputs": {"conditioning": ["364", 0], "run_name": "stream114-s00000001", "text": "A small red wooden toy boat drifts on calm water at sunset."}}
}
```

Values that vary per chunk:

- `run_name` is `stream114-s%08d` of `stream_seq`, identical on every node that has one.
- `338/339.noise_seed` is `seed`; `364.clip_index` is `11401000 + stream_seq`.
- `364.text` and `stream_text.text` are both the prompt.
- `364.qualification_id` depends on `frames`, `placement` and `anchor`; the status
  route returns it. The eight values are in `stream-plan.json` → `qualification_ids`
  (key `frames/placement/anchor`).
- `356.length`, `366.frames_number` and `stream_output.frames` are all `frames`.
- `stream_output` also carries `placement`, `anchor`, `scene_id`, `seed`,
  `stream_seq`, `chunk_index`, `predecessor_anchor_sha256` and `reuse_text`.
- `stream_anchor.predecessor_anchor_sha256` is the same hash as in `stream_output`.

The other shapes:

- **Chunk 0 and resets:** no `stream_anchor`, `stream_condition_a` or
  `stream_condition_b`; `377.video_latent` is `["356", 0]` and `340.video_latent`
  is `["348", 0]`; a reset adds `"reset": 1` to `stream_output.inputs`.
- **Text reuse (`reuse_text: 1`):** node `364` is absent, and `stream_text` has no
  `conditioning` input.
- **Frame anchor (`LTX_ANCHOR=frame`):** `stream_anchor` is
  `LTXStreamAnchor114 {run_name, predecessor_anchor_sha256}` and both condition
  nodes are `LTXStreamCondition114 {vae: ["420", 2], image: ["stream_anchor", 0],
  latent: …, strength: 1.0, bypass: false, run_name, stage}` (113's inputs).

There are no `VAEDecode`, `LTXVAudioVAEDecode` or capture nodes in any 114 graph.
`LTXGraphCaptureGate` and `LTXTextEncoderGraphGate` appear only in the eager and
graph qualification chains.

## 4. Admission responses

- **HTTP 200:** ComfyUI's normal `{"prompt_id": …, "number": …}`.
- **HTTP 400:** malformed body: `contract`, `missing-client-id`, `missing-prompt-id`.
- **HTTP 409** (nothing latched; fix and resubmit): `busy`, `order`,
  `stale-anchor`, `contract` (graph differs from `build_chunk_graph(params)`, or
  `frames`/`placement`/`anchor` differ from the server), `text-reuse-rule`,
  `text-cache-missing`, `window-not-captured`, `window-not-qualified`,
  `not-streaming`, `not-prepared`, `storage`, `precheck-error`.
- **HTTP 503 `halted`:** the server is latched. See §8.

## 5. Text handling

- **Default `LTX_STREAM_TEXT_REUSE=1`:** when the prompt equals the previous
  chunk's prompt (and the chunk is not a reset), the client **must** send
  `reuse_text: 1`; the server serves a copy of its single cached encode, the
  chain's latest fresh encode of that prompt. On a cut send `reuse_text: 0`; the
  new prompt is encoded and becomes the cache. Exactness: the live 113 server
  qualified reuse against fresh encodes byte-identical on 2026-10-08, and 114's
  qualification exercises reuse at chunk 1 of the graph and repeat chains.
- **`LTX_STREAM_TEXT_REUSE=0`:** every chunk re-encodes; `reuse_text` is always 0.
- **Text window rule** (unchanged): the encoder pads to the smallest captured
  window bucket that holds the prompt; a prompt outside the qualified bucket
  (64 rows, roughly up to 60 Gemma tokens) is refused with
  `window-not-qualified`, not latched. Status → `qualified_text_windows`.

## 6. Completion, the receipt, the decode record and the preview record

- **Completion signal:** WebSocket `execution_success` for your `prompt_id` once
  the receipt is committed, or poll `GET /ltx-stream/receipt/<run_name>` (404
  until committed). `execution_error` means the server halted.
- **Receipt file:** `<server run dir>/receipts/receipt-<run_name>.json`, written
  once (exclusive create plus fsync) at **anchor ready**. The run dir is
  `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-114-<anchor>-<placement>-w1-b1-p1-dxpu2-s256x256-f<frames>`
  (status → `receipt_dir`).

Receipt fields (schema `ltx.stream114.chunk-receipt.v1`):

| field | meaning |
|---|---|
| `run_name`, `prompt_id`, `kind`, `stream_seq`, `chunk_index`, `scene_id`, `seed`, `frames`, `placement`, `anchor` | identity |
| `prompt_sha256`, `prompt_changed` (`null` for chunk 0), `reuse_text`, `server_text_reuse` | text |
| `text.reused`, `text.tensors[]` | SHA-256 of every conditioning tensor actually fed to the samplers |
| `tensors.{video_latent,audio_latent,stage_a_latent}` | `shape`, `dtype` (`torch.float32`), `finite: true`, `sha256` of the complete little-endian F32 payload. Shapes at 49 / 97: video `[1,128,7,8,8]` / `[1,128,13,8,8]`, audio `[1,8,51,16]` / `[1,8,101,16]`, stage A `[1,128,7,4,4]` / `[1,128,13,4,4]` |
| `anchored`, `reset`, `reset_predecessor_anchor_sha256` | as 113 |
| `anchor_in` | `null` when unanchored; otherwise `{kind, sha256, path, source_run_name}` |
| `anchor_out` | latent: `{kind: "latent", sha256, path (…/anchors/<run>.latent.f32), bytes: 40960, slot: T-1, layout: [{part: "A", shape [1,128,1,4,4], offset 0, bytes 8192, source "367 video_latent slot T-1"}, {part: "B", shape [1,128,1,8,8], offset 8192, bytes 32768, source "369 …"}], dtype "F32", byte_order "little"}`. frame: `{kind: "frame", sha256, path, bytes: 786432, frame_index: frames-1, shape: [1,256,256,3], dtype, byte_order}`. **Send `sha256` as the next chunk's `predecessor_anchor_sha256`.** |
| `slot0_pin` | latent and anchored only, diagnostic: for `A` and `B`, does the stage output's slot 0 equal the anchor bytes (`bytes_equal`), or differ only by signed zero (`differing_all_signed_zero`; the sampler blend turns a −0.0 anchor element into +0.0), plus counts. Never gated. `null` otherwise |
| `delivery` | `{frames_total, fps: 24, new_frames, first_new_frame_index, drop_leading_frames, overlap}`. Anchored chunks: **drop 1 leading frame** (48 new at 49 = 2.0 s, 96 new at 97 = 4.0 s). Chunk 0 and resets deliver all frames |
| `decode` | `{state: "queued" (latent) \| "done" (frame), device: "xpu:3", record (absolute path of the decode record), queue_depth_at_submit, submit_blocked_s}` (+ `sequence` when done) |
| `preview` | `{path (absolute .mp4, final name), relative_to_output_directory, state: "queued", bytes: null, record, container: "mp4", lossy: true, fps: 24, frames, includes_overlap_frame}` |
| `predecessor_decode`, `predecessor_preview` | summaries of the previous chunk's decode/preview records if committed by the time this receipt was staged, else `null` |
| `decode_at_start` | `{drained, pending, current}`: the decode thread's state when this request started (`pending > 0` means the previous decode overlapped this chunk) |
| `capture` | qualification only: `{path …/output/validation/<run>/tensors.safetensors, writer: "decode thread", record}` |
| `timing_ns` | wall-clock ns: `submit`, `execution_start`, node starts `text_start` (364), `sampler_a_start` (344), `stage_a_done` (367), `upsampler_start` (348), `condition_b_start`, `concat_b_start` (340), `sampler_b_start` (368), `stage_b_done` (369), `output_start`; then **`anchor_ready`**, `decode_queued`, `decode_done` (frame only; `null` with latent), `preview_written` (always `null`), `receipt_staged`. A node absent from the graph (364 on reuse, the condition node on unanchored chunks) has `null` |
| `timing_s` | `submit_to_sampler_start`, `sampler_a_bucket` (344→368, as 113's), `sampler_a_split` {`sampler_a`, `separate_to_upsampler`, `upsampler_to_condition_b`, `condition_b_to_concat`, `concat_to_sampler_b`}, `sampler_b` (368→369), `stage_b_done_to_anchor_ready`, **`submit_to_anchor_ready`** (the chain's per-chunk lag), `anchor_ready_to_receipt_staged`, `decode_in_chain` and `submit_to_decode_done` (frame only), `submit_to_preview_written` (`null`) |
| `graph`, `memory`, `storage`, `sanity`, `committed`, `commit_ns`, `plan_sha256`, `qualification_id`, `qualification_verdict_sha256`, `server_identity_sha256`, `runtime_manifest_sha256` | as 113 |

### 6a. The decode record (packet 114)

`receipts/decode-<run_name>.json`, schema `ltx.stream114.decode-record.v1`,
served by `GET /ltx-stream/decode/<run_name>` (404 until written; 503 `halted`
after a decode failure). Validate with
`stream_receipts.validate_decode_record(record, receipt)`.

- `tensors.{images, waveform}`: shape, dtype, finite, SHA-256 of the decoded
  F32 payloads (images `[frames,256,256,3]`; waveform `[1,2,96480]` at 49,
  `[1,2,192480]` at 97).
- `last_frame_sha256`; with `frame`, `frame_anchor {sha256, bytes}` equals the
  receipt's `anchor_out`.
- `anchor_diagnostics`: 113's border-vs-centre diagnostic, computed on the
  decoded last frame (moved here from the receipt; same computation, comparable).
- `capture` (qualification chunks): the capture path and its prewrite evidence.
- `sequence` (1, 2, … in submission order), `order: "fifo"`, `device: "xpu:3"`,
  `xpu3_free_before_decode`.
- `timing_ns {submit, anchor_ready, decode_queued, decode_start, decode_done}` and
  `timing_s {queue_wait, decode, anchor_ready_to_decode_done, submit_to_decode_done}`.

### 6b. The preview record and the bounded wait rule

As 113 §6a, behind the decode thread: the writer encodes the MP4 under a hidden
`.partial` name, fsyncs, hard-links it to the final name, then commits
`receipts/preview-<run_name>.json` (schema `ltx.stream114.preview-record.v1`,
timing keys `submit, decode_done, preview_queued, write_start, preview_written`,
and `timing_s.decode_done_to_preview_written`). One writer, FIFO, two waiting
previews, back-pressure onto the decode thread; no preview is ever dropped.

**Wait rule.** After the receipt of chunk `n` exists:

1. Submit chunk `n+1` (you only need `anchor_out.sha256`).
2. Poll `GET /ltx-stream/preview/<run_name of n>` (404 until committed).
3. Give up after a bound (the client's `--save-wait`; 30 s for `--packet 114`,
   because at 97 frames the MP4 follows a ~2 s decode). 503 `halted`: stop. A
   timeout without a halt: stop and report (client exit 7). Do not resubmit.
4. Use the MP4 only once the record exists and the file's size and SHA-256 equal
   the record's.

A decode or preview failure latches the server
(`stream-decode-failure-<run>.json` / `stream-preview-failure-<run>.json`,
`halted` set, later posts get 503). Jobs queued behind a failure are not run.
If the server is stopped while a decode or preview is queued, that chunk may be
left without a decode/preview record; its receipt and anchor are still valid.

**Audio.** Each chunk has 96,480 samples (2.01 s) at 49 frames and, by the
sealed formula, 192,480 samples (4.01 s) at 97 frames, against 2.04 s / 4.04 s of
video; no trim or alignment rule is defined (owner decision pending, as 113).

## 7. Other routes

- `GET /ltx-stream/status`: `phase`, `halted`, `fault`, `active`,
  `next_stream_seq`, `stream_completed`, `frames`, `placement`, **`anchor`**,
  `text_reuse`, `qualification_id`, `chain`, `last_stream_receipts`,
  `qualified_text_windows`, `storage`, `receipt_dir`, `output_directory`,
  `packet: 114`, `features {latent_anchor, decode_thread, async_preview,
  chain_reset, anchor_diagnostics, chunk_length_choice, text_reuse_default_on}`,
  `decode_worker {submitted, completed, pending, current, failed,
  skipped_after_failure, maxsize}` and `preview_writer {…}`. 409 `busy` while the
  verdict action runs.
- `GET /ltx-stream/receipt/<run_name>`, `GET /ltx-stream/decode/<run_name>`,
  `GET /ltx-stream/preview/<run_name>`.
- `POST /ltx-stream/action {"action": "qualify-verdict"}`: qualification driver only, once.

## 8. Halts, bounds and what the client must not do

- Any exception inside an admitted chunk, the decode thread or the preview writer
  latches the server: a memory floor (including the 9 GiB xpu:3 floor checked
  before every decode), a route or signature change, nonfinite output, a geometry
  difference (at 97 frames the first eager chunk records the measured shapes in
  `stream-geometry-measured.json`, or `stream-geometry-mismatch-<run>.json` before
  latching), a storage limit or a device fault. Every later POST gets 503
  `halted`. Nothing is retried or restarted. The client must stop and report; it
  must never resubmit in a loop or signal the server.
- **Back-pressure, not drops:** the decode queue holds two waiting chunks. A full
  queue makes the next chunk's output node wait. A queue that does not move for
  120 s is a fault (latch).
- **Storage:** at most 3 GiB net consumption since launch while keeping 50 GiB
  free (captures, previews, records, anchors). The server keeps the two newest
  anchor files of the stream chain. The client may delete preview MP4s it has
  consumed and nothing else.
- The client never uploads images, latents or tensors, and never names a server
  path in a request.
