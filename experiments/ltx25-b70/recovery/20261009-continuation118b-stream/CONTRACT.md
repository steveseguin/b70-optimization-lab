# Packet 118b rebuild note (read first)

118b supersedes withdrawn, never-launched sealed packet 118. Its parent is sealed 117,
manifest `5826174ee3a3965d033758de006552742878f624800dadb90423879b3f0802c9`.
As for 116b, wire schemas and node classes stay at the preceding packet's revision:
`ltx.stream118.*` and node classes ending in `118`. Packet id is the string `"118b"`;
names use `stream118b-`, comparison mode `stream-candidate-118b-v1`, and clip bases
11820000 / 11821000. Numerical contracts and qualification ids are unchanged from 118;
the new plan binds the renamed graphs. Request topology and tensor operations are unchanged.

Review corrections: P7 on the decode thread always compares the walk and fingerprint,
independent of successor requests; P5's actual free reading is observed. Near-floor uses
an inclusive 0.5 GiB boundary. Dual four-card checks compare each sample's memory admission
verdict using the site's before/after floor, plus the existing identity fields.
A disagreement still writes `snapshot-118-refused.json`; inherited decoder-116,
anchor-decode-117/118 and precompute-117/118 latches remain binding.

`queued` means POST-handler return and is refreshed at receipt staging. `first_served`
means successful read and construction of an HTTP 200 response, not delivery or completed
fsync. Missing and negative values remain visible. Split sums are accounting checks,
not proof of causal accuracy. Instrumentation adds unmeasured CPU overhead.
No XPU correctness or speed claim follows from this CPU rebuild.

# Packet 118b stream client contract

Packet 118b is packet 117 (frame anchor by default, the decoder graph, the cone anchor decode, the stage-A/B encodes
on the decode thread, 49/97/121-frame chunks) plus three server-side levers that do not change a request graph or
an output byte, and its own names. Everything in the packet-117 contract below still holds, with these changes.
Client: `ltx_continuation_client.py --packet 118b [--expect-anchor frame] [--expect-decoder-graph 0|1]
[--expect-anchor-decode full|cone] [--expect-bencode-overlap 0|1] [--expect-prep-ahead 0|1]
[--expect-snapshot-mode walk|fingerprint] [--expect-pool-cap-gb GB]`.

## What changed from packet 117 (read this first)

1. **Identity.** `packet` is the string `"118b"`; names carry `stream118b-` (`stream118b-s%08d`,
   `stream118b-q{eager,graph,repeat}-c00000k`); clip index bases `11820000` (qualification) and `11821000`
   (stream); comparison mode `stream-candidate-118b-v1`; schemas `ltx.stream118.chunk-receipt.v1`,
   `ltx.stream118.decode-record.v1`, `ltx.stream118.preview-record.v1`, `ltx.stream118.qualification-verdict.v1`.
   The 132 qualification ids are new values over the same 132 keys (`frames/placement/anchor/dg/ad/bo/pa`).
2. **The request graph is packet 117's form.** `stream_params(...)` and `build_chunk_graph(params)` take the same
   arguments; the three 117 lever fields stay request fields. The two new launch options below are NOT request
   fields and NOT part of the qualification id: send nothing new.
3. **Two server-side launch options**, returned by `GET /ltx-stream/status` and recorded in every receipt as
   `server_options {snapshot_mode, decoder_graph_pool_cap_bytes}`:

   | status field | values | launch variable | what the server does |
   |---|---|---|---|
   | `snapshot_mode` | `"fingerprint"` (default), `"walk"` | `LTX_SNAPSHOT_MODE` | how each four-card safety snapshot checks residence: `walk` = packet 117 (every tensor serialised and hashed per snapshot); `fingerprint` = the same checks with the residence from fact tuples bound to the admitted fingerprints (the walk itself whenever any fact differs). Qualification snapshots run both and must agree; streaming runs both on every 20th chunk and from any near-floor reading on |
   | `decoder_graph_pool_cap_bytes` | `null` (default) or bytes | `LTX_DECODER_GRAPH_POOL_CAP_GB` | `null` = packet 117. Set: decoder methods are captured in first-call order while the measured pool growth of the captures already made is below the cap; a capped method decodes eagerly with the same caches (byte-gated as before) |

   The run name carries the snapshot mode (`-sm<walk|fp>-`), not the pool cap. `features` adds `timing_split: true`,
   `snapshot_fingerprint` (true in fingerprint mode) and `decoder_graph_pool_cap`; status adds `snapshot_state`
   (mode, dual policy, the residence ledger's counters: fingerprint snapshots, fallback walks, dual walks,
   agreements, disagreements).
4. **Receipts** (`ltx.stream118.chunk-receipt.v1`) add, all measurement only:
   - `timing_ns` marks `admission_received` (the POST reached the server), `precheck_done`, `queued` (ComfyUI
     handler returned; refreshed at receipt staging), `executor_entry`, `request_snapshot_start/done`, `before_request_done`, the node
     starts `stream_text_start`, `anchor_start`, `condition_a_start`, `concat_a_start`, and
     `condition_a_lookup_done`, `condition_a_done`, `condition_b_lookup_done`, `condition_b_done`;
   - `node_starts_ns`: every node's first `executing` event of the request;
   - `timing_s.submit_split`: `submit_to_sampler_start` split into `precheck`, `comfy_validate_queue`,
     `queue_to_executor`, `authority_begin`, `before_request_checks`, `request_before_snapshot`,
     `before_request_tail`, `executor_to_first_node`, `first_node_to_condition_a` (text window/reuse, anchor read),
     `condition_a_lookup`, `condition_a_tail` (the guarded stage A: `stage_a_before_snapshot`, `stage_a_consume`,
     `stage_a_after_snapshot` inside it), `dispatch_to_sampler_a`, plus `other` (whatever no mark covers) and
     `total`; the tiles plus `other` equal `submit_to_sampler_start` exactly;
   - `snapshots`: each four-card snapshot of the request in order (`request-before`, `A-before`, `A-after`,
     `B-before`, `B-after`, `request-after`; unanchored chunks only the two request ones), with `mode`, `dual`
     (the walk ran beside the fingerprint), `agree` (true when dual), `start_ns`, `end_ns`, `seconds`, `parts_s`
     (state, facts, residence, memory; or the walk; or `dual_walk` and `dual_fingerprint`) and `min_margin_bytes`
     (smallest card margin above its pre-request floor);
   - `authority_checks`: `healthy_calls`, `healthy_s`, `plan_digest_s` (the authority's plan-identity check),
     `status_route_calls`, `status_route_s` (the status route's own cost) during the request;
   - `turnaround` (anchored chunks): the predecessor's receipt -> this submit: `marks_ns` (`receipt_staged`,
     `commit`, `commit_written`, `executor_exit`, `first_served` = first successfully constructed HTTP 200 response for the predecessor's receipt
     route, `admission_received`, `submit`), `split` (`receipt_staged_to_commit`, `commit_write`,
     `commit_to_first_served`, `served_to_admission`, `admission_parse`, `other`, `total`),
     `receipt_polls_before_served` (404s of the receipt route) and `commit_to_executor_exit_s`.
5. **Decode records** add `decoder.pool {cap_bytes, growth_bytes, captured, capped, capped_calls, rule}` (null
   with `decoder_graph: 0`).
6. **Verdict** adds `server_options`, `snapshot_rows` (per qualification chunk: labels, modes, dual, agree,
   seconds), `snapshot_failures` and per decoder row `pool`.
7. **Halts and latches.** Besides 117's: a fingerprint snapshot that disagrees with its walk latches the server and
   writes `snapshot-118-refused.json` in the results root (the launcher then refuses `LTX_SNAPSHOT_MODE=fingerprint`).
   The cone and precompute latches are now `anchor-decode-118-refused.json` and `precompute-118-refused.json`; the
   launcher refuses those levers while either the 118 or the 117 latch exists. `decoder-graph-116-refused.json` stays
   shared. A moved or replaced tensor is refused the same way in both snapshot modes (the walk decides).
8. **Client turnaround.** `--packet 118b` manifest lines add `submit_split`, the snapshot summary, `authority_checks`,
   the server's `turnaround` split and the client's own `client_turnaround_s` (receipt verified -> next POST) and
   `client_post_s`.

---

# The packet 117 contract (with 118b names)

Packet 117 is packet 116b (frame anchor by default, 116a scheduling, the decoder graph, the packet-113/114
frame references, the NA axis-router acceptance) plus four launch-selectable levers for the frame anchor,
121-frame chunks, and its own names. Everything in the packet-116 contract below still holds, with these
changes. Client: `ltx_continuation_client.py --packet 118b (or 117) [--expect-anchor frame] [--expect-decoder-graph 0|1]
[--expect-anchor-decode full|cone] [--expect-bencode-overlap 0|1] [--expect-prep-ahead 0|1]`.

## What changed from packet 116b (read this first)

1. **Identity** (packet 118's values; 117 had its own). Names carry `stream118b-` (`stream118b-s%08d`,
   `stream118b-q{eager,graph,repeat}-c00000k`); clip index bases `11820000` (qualification) and `11821000`
   (stream); comparison mode `stream-candidate-118b-v1`; schemas `ltx.stream118.chunk-receipt.v1`,
   `ltx.stream118.decode-record.v1`, `ltx.stream118.preview-record.v1`,
   `ltx.stream118.qualification-verdict.v1`.
2. **Chunk length 121** (`LTX_STREAM_FRAMES=121`, 5.04 s): 16 latent frames, 256 stage-A and 1024 stage-B
   video tokens; shapes at 121: video latent `[1,128,16,8,8]`, stage A `[1,128,16,4,4]`, audio latent
   `[1,8,126,16]`, images `[121,256,256,3]`, waveform `[1,2,240480]` (5.01 s). The audio shapes come from the
   sealed formulas (`round(121/24*25) = 126`, `((126-1)*4+1)*480 = 240480`, the formula the measured 49 and
   97 lengths satisfy); the first eager chunk of the launch checks them and writes
   `stream-geometry-measured.json`, or `stream-geometry-mismatch-<run>.json` and halts. An anchored 121-frame
   chunk delivers 120 new frames (5.0 s).
3. **Three lever fields in every request** (launch parameters, returned by `GET /ltx-stream/status`, part of
   the qualification id). For `anchor != "frame"` they must be `"full"`, `0`, `0`.

   | field | type | values | launch variable | what the server does |
   |---|---|---|---|---|
   | `anchor_decode` | str | `"cone"` (default), `"full"` | `LTX_ANCHOR_DECODE` | `cone`: the anchor frame comes from a decode that computes only what the last pixel frame depends on; the full decode for display follows on the decode thread and must equal it byte for byte |
   | `bencode_overlap` | int | `1` (default), `0` | `LTX_BENCODE_OVERLAP` | `1`: the stage-B anchor encode runs on the decode thread beside stage A |
   | `prep_ahead` | int | `1` (default), `0` | `LTX_PREP_AHEAD` | `1`: the stage-A anchor encode runs on the decode thread right after the predecessor's receipt commits |

   None of them changes a byte of any output: each is exact by construction and gated by the
   qualification (eager chain with every lever off against the graph and repeat chains with them on), and
   each has a latch file that makes the launcher refuse it after a failure. In the graph,
   `stream_output.inputs` carries `anchor_decode`, `bencode_overlap` and `prep_ahead` next to
   `decoder_graph`; `364.qualification_id` is one of the 132 ids in `stream-plan.json` → `qualification_ids`,
   key `frames/placement/anchor/dg0|dg1/ad-full|ad-cone/bo0|bo1/pa0|pa1`. Build every graph with
   `stream_contract.stream_params(..., anchor_decode=status['anchor_decode'],
   bencode_overlap=status['bencode_overlap'], prep_ahead=status['prep_ahead'])` and
   `build_chunk_graph(params)`; a request whose levers differ from the server's is refused `contract`.
4. **When the receipt commits** (frame anchor): still at anchor ready, right after the anchor decode and the
   anchor file (`decode.state: "video_done"`; `timing_ns.video_done` is the end of the decode the chain
   waited for: the cone decode with `anchor_decode: "cone"`). The display decode, the stage-A/B
   precomputes, the audio decode, hashing, the decode record and the MP4 follow on the decode thread; with
   `cone` or `bencode_overlap` the decode thread waits (bounded 3 s) until the NEXT chunk's sampler A has
   started before the display decode, so the decode record and the preview of chunk `n` arrive after chunk
   `n+1` has started (`--save-wait` 30 s still covers it). Submit chunk `n+1` right after receipt `n`, as before.
5. **Receipts** add `levers {anchor_decode, bencode_overlap, prep_ahead}` and, for anchored frame chunks,
   `conditioning_sources {A, B}`: per stage `{stage, lever ("prep_ahead" for A, "bencode_overlap" for B),
   lever_on, source ("native" | "precomputed" | "native-inline"), reason, waited_s, dual_equal, precompute}`.
   `native-inline` means the lever was on but no precomputed encode was available for this anchor (for
   example after a reset); the stage then ran the native encode itself (exact, slower). `dual_equal` is set
   only in the graph qualification chain, which runs both. `timing_s.anchor_decode_in_chain` is the anchor
   decode the chain waited for.
6. **Decode records** add `levers`, `anchor_decode {mode, flag, seconds, last_frame_sha256, plan,
   display_seconds, display_last_frame_sha256, equal}` (`equal` is true on every cone chunk; a false value
   never reaches a record: the server latches first), `precompute {A, B}` (the encodes the decode thread
   prepared for the NEXT chunk, with their xpu:3 safety snapshots), `schedule {gated, levers_live, commit,
   commit_wait_s, go ("sampler-a-start" | "bound"), go_wait_s}`, and the timestamps `precompute_a_start/done`,
   `go`, `precompute_b_start/done`, `display_start/done` (null unless that step ran), with
   `timing_s.precompute_a`, `precompute_b`, `anchor_ready_to_go`, `display_decode`. Order on the decode thread:
   anchor decode → anchor file → hand-off → stage-A encode → go → stage-B encode → display decode → audio →
   hashes → record → preview.
7. **Status** adds `anchor_decode`, `bencode_overlap`, `prep_ahead`, `anchor_decode_state`, `precompute_state`
   and `features.cone_anchor_decode`, `features.bencode_overlap`, `features.prep_ahead`, `features.chunk_121`
   (`features.bencode_overlap` is now the launch value).
8. **Verdict** adds `levers`, `lever_rows` (per chunk: anchor decode mode, cone equality, stage sources,
   dual equality, precompute waits), `anchor_decode_failures` and `precompute_failures`.
9. **Halts.** Besides 116b's: a cone anchor that differs from its display decode
   (`anchor-decode-118-refused.json` in the results root), a precomputed encode whose guard refuses (xpu:3
   below 9 GiB before / 2 GiB after, residence, fault, phase, encoder cache) or whose graph-chain dual check
   differs (`precompute-118-refused.json`). The launcher refuses `LTX_ANCHOR_DECODE=cone` while the first
   exists and `LTX_BENCODE_OVERLAP=1` or `LTX_PREP_AHEAD=1` while the second exists. The decoder-graph latch
   stays `decoder-graph-116-refused.json`.

The packet-116 contract follows unchanged except for the names (`stream118b-…` everywhere `stream116b-…`
appears, `packet: 118`, the clip bases and comparison mode above) and the additions listed here.

---

# The packet 116 stream client contract (with 118b names)

## What changed from packet 115 (read this first)

Packet 116 keeps 115's request model (one anchor chain, one request at a time, strict
`stream_seq` order, the predecessor named by its anchor hash, chain resets, the decode thread,
49/97-frame chunks, text reuse on by default, the four anchor modes, the admission codes, the
floors and the latches). What changes for a client:

1. **The default anchor is `frame`** (`LTX_ANCHOR=frame`, packet113 semantics at both stages:
   chunk `n-1`'s decoded last frame through the native image conditioning with its VAE encode).
   It is the only measured mode whose first frames are as sharp as mid-chunk. `mixed`, `latent`
   and `guide` remain launch options, unchanged from 115.
2. **116a: the frame receipt commits after the VIDEO decode.** The decode thread decodes the
   video, writes the decoded last frame as the anchor file (exclusive, finiteness-checked,
   fsynced) and hands it to the chain; the receipt (`decode.state: "video_done"`,
   `timing_ns.video_done <= anchor_ready`) is committed and you may submit chunk `n+1`. The audio
   decode, the tensor hashes, the diagnostics, the decode record and the MP4 follow on the decode
   thread. So with `frame` the decode record of chunk `n` arrives **after** its receipt (as with
   the other modes since 114): wait for `GET /ltx-stream/decode/<run>` before the preview, as for
   `--packet 115`.
3. **`decoder_graph` is a launch parameter and a request field** (`LTX_DECODER_GRAPH`, `1` by
   default; status → `decoder_graph`). Every chunk's `stream_output` carries
   `"decoder_graph": 0|1` and it enters the qualification id (32 ids, key
   `frames/placement/anchor/dg0|dg1`). The server replays the NA video decoder from XPU graphs
   with bounded caches (RoPE inverse frequencies, NA window masks, the seed-0 decoder noise),
   qualified by byte identity against the uncached eager decode; nothing about the outputs
   changes if the gate passes. A mismatch latches the server and the launcher then refuses graph
   mode (no automatic fallback).
4. **Receipts** (`ltx.stream116.chunk-receipt.v1`): new `decoder_graph`, `timing_ns.video_done`,
   `timing_s.video_decode_in_chain` / `video_done_to_anchor_ready`; `decode.state` is `"done"` for
   eager/graph qualification chunks in every mode (they wait for the whole decode), `"video_done"`
   for frame stream chunks, `"queued"` otherwise; `timing_ns.decode_done` is set only with
   `"done"`.
5. **Decode records** (`ltx.stream116.decode-record.v1`): split timestamps `video_done`,
   `audio_done`, `hashed`, `record_staged` (`decode_done = audio_done`); a `decoder` block
   (§6a); `frame_anchor.path` for the frame anchor too. **Preview records**
   (`ltx.stream116.preview-record.v1`) add `video_done`, `anchor_ready`, `audio_done`, `hashed`,
   `record_written`.
6. **Names**: `stream118b-…`; node classes `…116`; clip index base `11821000`. A 115 graph builder
   does not produce valid 116 requests.
7. **Qualification** adds the decoder-graph rows and, for the frame anchor at
   49/two-way20-28 and 97/two-way20-28, a cross-packet check: the eager chain must equal the
   live packet-113 (49) / packet-114 frame (97) qualification byte for byte
   (`resolution/reference-frame-hashes.json`).
8. **Client:** `ltx_continuation_client.py --packet 118b (or 117) [--expect-anchor frame|mixed|latent|guide]
   [--expect-decoder-graph 0|1] [--expect-anchor-decode full|cone] [--expect-bencode-overlap 0|1]
   [--expect-prep-ahead 0|1]` (packet 117: the levers are request fields, see the top of this file).

### Graph forms

Unchanged from 115 apart from the class names (`…116`) and the new `stream_output.decoder_graph`
input. Frame anchor (default), chunk `n > 0`: `stream_anchor` = `LTXStreamAnchor116
{run_name, predecessor_anchor_sha256}`; `stream_condition_a` / `stream_condition_b` =
`LTXStreamCondition116 {vae: ["420",2], image: ["stream_anchor",0], latent: ["356",0] / ["348",0],
strength: 1.0, bypass: false, run_name, stage: "A" / "B"}`. Mixed, latent and guide forms: 115's
contract §"Graph forms" with `115` → `116`. Build every graph with
`stream_contract.build_chunk_graph(params)`; the server compares canonical JSON and refuses anything
else.

---

This is the request format for the packet 116 continuation stream server. It is
written for whoever builds the streaming client. The server listens on
`http://127.0.0.1:8188`. It is the ordinary ComfyUI `/prompt` endpoint, with an
admission layer in front of it and five extra routes.

The server accepts exactly one graph per parameter set. The reference builder is
`stream_contract.py`. It is stdlib-only, so import it rather than
hand-assembling JSON. The sealed copy is at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118b/resolution/components/stream_contract.py`.

```python
import stream_contract as c
status = GET /ltx-stream/status     # frames, placement, anchor, decoder_graph, next_stream_seq, chain.anchor_sha256, text_reuse
params = c.stream_params(status['frames'], stream_seq, prompt, seed, predecessor_anchor_sha256, scene_id,
                         reuse_text, placement=status['placement'], reset=0, anchor=status['anchor'],
                         decoder_graph=status['decoder_graph'])
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
| `frames` | int | must equal the server's `LTX_STREAM_FRAMES` (`49`, `97` or `121`); status → `frames` |
| `placement` | str | must equal the server's `LTX_SAMPLER_PLACEMENT` (`"two-way"` or `"two-way20-28"`); status → `placement` |
| `anchor` | str | must equal the server's `LTX_ANCHOR` (`"frame"` default, `"mixed"`, `"latent"` or `"guide"`); status → `anchor` |
| `decoder_graph` | int | must equal the server's `LTX_DECODER_GRAPH` (`1` default or `0`); status → `decoder_graph` |
| `anchor_decode` | str | must equal the server's `LTX_ANCHOR_DECODE` (`"cone"` default or `"full"`; `"full"` unless the anchor is `frame`); status → `anchor_decode` |
| `bencode_overlap` | int | must equal the server's `LTX_BENCODE_OVERLAP` (`1` default or `0`; `0` unless frame); status → `bencode_overlap` |
| `prep_ahead` | int | must equal the server's `LTX_PREP_AHEAD` (`1` default or `0`; `0` unless frame); status → `prep_ahead` |
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

### The graph for chunk n > 0 (97 frames, latent anchor, fresh text encode; the mixed and guide forms differ as listed at the top)

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
  "364": {"class_type": "LTXPipelineTextEncode", "inputs": {"clip": ["420", 1], "clip_index": 11801001, "comparison_mode": "stream-candidate-118b-v1", "depth": 2, "mode": "pipeline-window", "output_size": "256x256", "qualification_id": "<frames/placement/anchor/dgN id from the plan>", "run_name": "stream118b-s00000001", "speed_only": false, "text": "A small red wooden toy boat drifts on calm water at sunset."}},
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
  "stream_anchor": {"class_type": "LTXStreamLatentAnchor116", "inputs": {"predecessor_anchor_sha256": "ffff…(64 hex)", "run_name": "stream118b-s00000001"}},
  "stream_condition_a": {"class_type": "LTXStreamLatentCondition116", "inputs": {"anchor": ["stream_anchor", 0], "latent": ["356", 0], "run_name": "stream118b-s00000001", "stage": "A", "strength": 1.0}},
  "stream_condition_b": {"class_type": "LTXStreamLatentCondition116", "inputs": {"anchor": ["stream_anchor", 1], "latent": ["348", 0], "run_name": "stream118b-s00000001", "stage": "B", "strength": 1.0}},
  "stream_output": {"class_type": "LTXStreamChunk116", "inputs": {"anchor": "latent", "audio_latent": ["369", 1], "audio_vae": ["420", 3], "chunk_index": 1, "anchor_decode": "full", "bencode_overlap": 0, "decoder_graph": 1, "frames": 97, "kind": "stream", "placement": "two-way20-28", "predecessor_anchor_sha256": "ffff…(64 hex)", "prep_ahead": 0, "reuse_text": 0, "run_name": "stream118b-s00000001", "scene_id": "boat", "seed": 1001, "stage_a_latent": ["367", 0], "stream_seq": 1, "vae": ["420", 2], "video_latent": ["369", 0]}},
  "stream_text": {"class_type": "LTXStreamText116", "inputs": {"conditioning": ["364", 0], "run_name": "stream118b-s00000001", "text": "A small red wooden toy boat drifts on calm water at sunset."}}
}
```

Values that vary per chunk:

- `run_name` is `stream118b-s%08d` of `stream_seq`, identical on every node that has one.
- `338/339.noise_seed` is `seed`; `364.clip_index` is `11821000 + stream_seq`.
- `364.text` and `stream_text.text` are both the prompt.
- `364.qualification_id` depends on `frames`, `placement`, `anchor` and `decoder_graph`;
  the status route returns it. The 32 values are in `stream-plan.json` → `qualification_ids`
  (key `frames/placement/anchor/dg0|dg1`).
- `356.length`, `366.frames_number` and `stream_output.frames` are all `frames`.
- `stream_output` also carries `placement`, `anchor`, `decoder_graph`, `scene_id`, `seed`,
  `stream_seq`, `chunk_index`, `predecessor_anchor_sha256` and `reuse_text`.
- `stream_anchor.predecessor_anchor_sha256` is the same hash as in `stream_output`.

The other shapes:

- **Chunk 0 and resets:** no `stream_anchor`, `stream_condition_a` or
  `stream_condition_b`; `377.video_latent` is `["356", 0]` and `340.video_latent`
  is `["348", 0]`; a reset adds `"reset": 1` to `stream_output.inputs`.
- **Text reuse (`reuse_text: 1`):** node `364` is absent, and `stream_text` has no
  `conditioning` input.
- **Frame anchor (`LTX_ANCHOR=frame`):** `stream_anchor` is
  `LTXStreamAnchor116 {run_name, predecessor_anchor_sha256}` and both condition
  nodes are `LTXStreamCondition116 {vae: ["420", 2], image: ["stream_anchor", 0],
  latent: …, strength: 1.0, bypass: false, run_name, stage}` (113's inputs).

There are no `VAEDecode`, `LTXVAudioVAEDecode` or capture nodes in any 116 graph.
`LTXGraphCaptureGate` and `LTXTextEncoderGraphGate` appear only in the eager and
graph qualification chains.

## 4. Admission responses

- **HTTP 200:** ComfyUI's normal `{"prompt_id": …, "number": …}`.
- **HTTP 400:** malformed body: `contract`, `missing-client-id`, `missing-prompt-id`.
- **HTTP 409** (nothing latched; fix and resubmit): `busy`, `order`,
  `stale-anchor`, `contract` (graph differs from `build_chunk_graph(params)`, or
  `frames`/`placement`/`anchor`/`decoder_graph` differ from the server), `text-reuse-rule`,
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
  `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-118b-<anchor>-dg<0|1>-ad<full|cone>-bo<0|1>-pa<0|1>-sm<walk|fp>-<placement>-w1-b1-p1-dxpu2-s256x256-f<frames>`
  (status → `receipt_dir`).

Receipt fields (schema `ltx.stream116.chunk-receipt.v1`):

| field | meaning |
|---|---|
| `run_name`, `prompt_id`, `kind`, `stream_seq`, `chunk_index`, `scene_id`, `seed`, `frames`, `placement`, `anchor`, `decoder_graph` | identity |
| `prompt_sha256`, `prompt_changed` (`null` for chunk 0), `reuse_text`, `server_text_reuse` | text |
| `text.reused`, `text.tensors[]` | SHA-256 of every conditioning tensor actually fed to the samplers |
| `tensors.{video_latent,audio_latent,stage_a_latent}` | `shape`, `dtype` (`torch.float32`), `finite: true`, `sha256` of the complete little-endian F32 payload. Shapes at 49 / 97: video `[1,128,7,8,8]` / `[1,128,13,8,8]`, audio `[1,8,51,16]` / `[1,8,101,16]`, stage A `[1,128,7,4,4]` / `[1,128,13,4,4]` |
| `anchored`, `reset`, `reset_predecessor_anchor_sha256` | as 113 |
| `anchor_in` | `null` when unanchored; otherwise `{kind, sha256, path, source_run_name}` |
| `anchor_out` | latent: `{kind: "latent", sha256, path (…/anchors/<run>.latent.f32), bytes: 40960, slot: T-1, layout: [{part: "A", shape [1,128,1,4,4], offset 0, bytes 8192, source "367 video_latent slot T-1"}, {part: "B", shape [1,128,1,8,8], offset 8192, bytes 32768, source "369 …"}], dtype "F32", byte_order "little"}`. frame: `{kind: "frame", sha256, path, bytes: 786432, frame_index: frames-1, shape: [1,256,256,3], dtype, byte_order}`. **Send `sha256` as the next chunk's `predecessor_anchor_sha256`.** |
| `slot0_pin` | latent and anchored only, diagnostic: for `A` and `B`, does the stage output's slot 0 equal the anchor bytes (`bytes_equal`), or differ only by signed zero (`differing_all_signed_zero`; the sampler blend turns a −0.0 anchor element into +0.0), plus counts. Never gated. `null` otherwise |
| `delivery` | `{frames_total, fps: 24, new_frames, first_new_frame_index, drop_leading_frames, overlap}`. Anchored chunks: **drop 1 leading frame** (48 new at 49 = 2.0 s, 96 new at 97 = 4.0 s). Chunk 0 and resets deliver all frames |
| `decode` | `{state, device: "xpu:3", record (absolute path of the decode record), queue_depth_at_submit, submit_blocked_s}` (+ `sequence` when done). `state`: `"done"` for the eager and graph qualification chains (every mode waits for the whole decode); otherwise `"video_done"` (frame: the video decode and the anchor file are done, the rest follows) or `"queued"` (mixed, latent, guide) |
| `preview` | `{path (absolute .mp4, final name), relative_to_output_directory, state: "queued", bytes: null, record, container: "mp4", lossy: true, fps: 24, frames, includes_overlap_frame}` |
| `predecessor_decode`, `predecessor_preview` | summaries of the previous chunk's decode/preview records if committed by the time this receipt was staged, else `null` |
| `decode_at_start` | `{drained, pending, current}`: the decode thread's state when this request started (`pending > 0` means the previous decode overlapped this chunk) |
| `capture` | qualification only: `{path …/output/validation/<run>/tensors.safetensors, writer: "decode thread", record}` |
| `timing_ns` | wall-clock ns: `submit`, `execution_start`, node starts `text_start` (364), `sampler_a_start` (344), `stage_a_done` (367), `upsampler_start` (348), `condition_b_start`, `concat_b_start` (340), `sampler_b_start` (368), `stage_b_done` (369), `output_start`; then **`anchor_ready`**, `decode_queued`, `video_done` (frame only: the decode thread's video decode; `video_done <= anchor_ready`), `decode_done` (only when `decode.state` is `"done"`), `preview_written` (always `null`), `receipt_staged`. A node absent from the graph (364 on reuse, the condition node on unanchored chunks) has `null` |
| `timing_s` | `submit_to_sampler_start`, `sampler_a_bucket` (344→368, as 113's), `sampler_a_split` {`sampler_a`, `separate_to_upsampler`, `upsampler_to_condition_b`, `condition_b_to_concat`, `concat_to_sampler_b`}, `sampler_b` (368→369), `stage_b_done_to_anchor_ready`, **`submit_to_anchor_ready`** (the chain's per-chunk lag), `anchor_ready_to_receipt_staged`, `decode_in_chain` (frame: `decode_queued → anchor_ready`, what the chain waited for), `video_decode_in_chain`, `video_done_to_anchor_ready`, `submit_to_decode_done` (only with `decode_done`), `submit_to_preview_written` (`null`) |
| `graph`, `memory`, `storage`, `sanity`, `committed`, `commit_ns`, `plan_sha256`, `qualification_id`, `qualification_verdict_sha256`, `server_identity_sha256`, `runtime_manifest_sha256` | as 113 |

### 6a. The decode record (packet 114, with the 115 and 116 additions)

`receipts/decode-<run_name>.json`, schema `ltx.stream116.decode-record.v1`,
served by `GET /ltx-stream/decode/<run_name>` (404 until written; 503 `halted`
after a decode failure). Validate with
`stream_receipts.validate_decode_record(record, receipt)`.

- `tensors.{images, waveform}`: shape, dtype, finite, SHA-256 of the decoded
  F32 payloads (images `[frames,256,256,3]`; waveform `[1,2,96480]` at 49,
  `[1,2,192480]` at 97).
- `last_frame_sha256`; with `frame` and `mixed`, `frame_anchor {sha256, bytes, path}`
  (frame: the receipt's `anchor_out`, written by the decode thread before the hand-off).
- `decoder {flag, mode: "eager" | "graph", reference, video_decode_s, new_captures,
  captured_graphs_total, signatures, replays, frozen}` (116). `mode` is `graph` exactly when
  the server runs `LTX_DECODER_GRAPH=1` and the chunk is not in the eager chain; graph-chain
  chunks carry `reference {mode: "eager-uncached", equal: true, images_sha256, seconds}`, the
  uncached eager decode of the same latents.
- `anchor_diagnostics`: 113's border-vs-centre diagnostic, computed on the
  decoded last frame (moved here from the receipt; same computation, comparable).
- `capture` (qualification chunks): the capture path and its prewrite evidence.
- `sequence` (1, 2, … in submission order), `order: "fifo"`, `device: "xpu:3"`,
  `xpu3_free_before_decode`.
- `timing_ns {submit, anchor_ready, decode_queued, decode_start, video_done, audio_done,
  decode_done (= audio_done), hashed, record_staged}` (116 order: video decode → frame anchor
  hand-off → audio decode → hashes and diagnostics → record) and `timing_s {queue_wait,
  video_decode, video_done_to_anchor_ready, audio_decode, hash_and_diagnostics,
  capture_and_record, decode, anchor_ready_to_decode_done, submit_to_decode_done}`.

### 6b. The preview record and the bounded wait rule

As 113 §6a, behind the decode thread: the writer encodes the MP4 under a hidden
`.partial` name, fsyncs, hard-links it to the final name, then commits
`receipts/preview-<run_name>.json` (schema `ltx.stream116.preview-record.v1`,
timing keys `submit, video_done, anchor_ready, audio_done, decode_done, hashed, record_written,
preview_queued, write_start, preview_written`,
and `timing_s.decode_done_to_preview_written`). One writer, FIFO, two waiting
previews, back-pressure onto the decode thread; no preview is ever dropped.

**Wait rule.** After the receipt of chunk `n` exists:

1. Submit chunk `n+1` (you only need `anchor_out.sha256`).
2. Poll `GET /ltx-stream/preview/<run_name of n>` (404 until committed).
3. Give up after a bound (the client's `--save-wait`; 30 s for `--packet 116`,
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
  `next_stream_seq`, `stream_completed`, `frames`, `placement`, **`anchor`**, **`decoder_graph`**,
  `decoder_graph_state` (signatures, captures, replays, caches, frozen),
  `text_reuse`, `qualification_id`, `chain`, `last_stream_receipts`,
  `qualified_text_windows`, `storage`, `receipt_dir`, `output_directory`,
  `packet: 118`, `features {latent_anchor, mixed_anchor, guide_anchor, frame_anchor,
  decode_thread, async_preview, chain_reset, anchor_diagnostics, sharpness_diagnostic,
  chunk_length_choice, text_reuse_default_on, video_first_handoff, decoder_graph,
  bencode_overlap: false}`,
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
  latching), a storage limit, a device fault, or a decoder-graph refusal (a graph decode
  that differs from the uncached eager decode, a refused capture, a new signature after
  the freeze; these also write `decoder-graph-116-refused.json` in the results root, after
  which the launcher refuses `LTX_DECODER_GRAPH=1`). Every later POST gets 503
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
