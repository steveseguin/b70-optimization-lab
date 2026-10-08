# Continuation 113: preview off the chain, chain reset, border diagnostic (built, not launched)

**Outcome.** Packet 113 is built and sealed at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113`
(manifest `a23dbc94…f7f28b`, 112,614,223 bytes). It is the live packet 112 with:

- one speed lever: the preview write is taken off the chain;
- a client-requested chain reset;
- a per-chunk anchor border diagnostic.

The second lever, a graph-captured VAE decode, is **not** shipped. It cannot be
made exact without a cache (see below).

All four model paths are 112's files byte for byte: sampler, conditioning,
text, and decoder. So are the qualification graphs and qualification ids. Tests:
80 CPU tests pass, the 112 suite still passes (63), and the client tests pass
(46/46 at 112, 11/11 at 113). The launcher `--check-only` passes. Nothing ran on
a GPU, so nothing here shows the saving.

## Where the time goes today (live 112, last 40 receipts, medians)

| stage | seconds |
|---|---|
| queue (submit → execution) | 0.006 |
| text + stage-A prep | 0.77 |
| sampler A | 1.62 |
| sampler B | 1.00 |
| decode | 0.95 |
| output node: hashes, anchor, **MP4 write** | 0.30 |
| receipt staging (memory/route checks) | 0.10 |
| **commit → next submit (client poll)** | **0.41** |

The output node's 0.30 s is about 0.04 s of hashing (39.6 MB SHA-256 measured at
0.02 s here) and anchor fsync. The rest, about 0.2–0.25 s, is the
CreateVideo + SaveVideo encode.

## Lever 1: the preview leaves the chain

**What it does.** The output node still does, in order, everything the next chunk
needs:

1. Checks and hashes the four tensors.
2. Writes and fsyncs the anchor file.
3. Stamps `anchor_ready`.
4. Computes the border diagnostic.

It then gives the MP4 job to **one writer thread** (`stream_preview.py`) and
returns. The receipt is committed as usual and the next chunk can be admitted.

- **Back-pressure.** The queue holds two waiting previews. A full queue makes
  the next output node wait, so no preview is dropped. Writes happen in order on
  one thread.
- **Private copies.** The writer gets private CPU copies (`clone`). A test makes
  an adversarial writer overwrite its copy and shows the hashed tensors and
  anchor are untouched.
- **Same encoder calls.** The writer calls the same `CreateVideo.execute` and
  `save_to` as 112's `save_preview`, with the same arguments. A test compares
  them against the sealed file. It writes to a hidden `.partial` name, fsyncs,
  then hard-links to the final name, so the MP4 path never shows a partial file.
- **Preview record.** It then commits `receipts/preview-<run>.json` with the
  bytes, the SHA-256 and the time written. `GET /ltx-stream/preview/<run>`
  serves it.
- **Failures latch.** A failed write records
  `stream-preview-failure-<run>.json` and halts the authority from a separate
  thread. That avoids deadlocking against the executor, which may hold the
  authority lock while waiting on a full queue. The status route reports
  `fault`, and later requests are refused.

**Why not packet 91's `PreviewWriter` object itself.** 112's stream graph wrote
the MP4 inline from the output node. It used the registered `save_preview`, not
the writer. Reusing packet 91's `_WRITER` instance would break two inherited
rules:

- The runtime observer's quiescence check requires that instance's pending count
  to be 0 at every request start and finish.
- Its guarded save turns write failures into a log entry, while the stream must
  latch.

So 113 uses a separate instance of the same design: one thread, bounded FIFO,
blocking submit, private copies.

**The client contract changes in one place.** The receipt now says
`preview.state: "queued"`, `bytes: null`, `timing_ns.preview_written: null`. The
client rule is to submit the next chunk, then wait at most 10 s for the preview
record, and use the MP4 only when the record matches the file. The chain's
latency is now `timing_s.submit_to_anchor_ready`. The MP4 latency is in the
record. The 112 client works with `--packet 113`. That flag selects the sealed
113 hashes and turns on the wait rule, and it is the only change.

**Exactness.** The four tensors, the anchor and every numerical source are
unchanged by construction. CPU tests show the anchor the next chunk is handed
is the bytes hashed into `anchor_out`, rebuilt by the same provider path. That
holds while a writer holds and scribbles on its copy, and that copy never
aliases the source. Qualification runs the same asynchronous writer in all
three chains, so the 9-chunk byte equality also covers the overlap. The verdict
waits (bounded) for all nine previews.

**Expected saving.** About 0.2–0.25 s per chunk off the 4.63 s, which takes
`submit_to_anchor_ready` to about 4.4 s. It is less than the 0.30 s target
because hashing and the anchor must stay on the chain.

## Lever 2: graph-captured VAE decode, not shipped

The brief's premise was that `ltx_graph_vae.py`/`graph_vae_node.py` were measured
exact for the 25-frame lane. The notes say otherwise.

`notes/vae-graph-capture-blocked-01.md`, fourth attempt (2026-09-16): decoder
capture failed its own bitwise proof. The decoder builds its RoPE tables inside
the forward. In `na_diffusion_decoder.py:77-83,137`, `rope_inv_freqs` does
`torch.tensor(float(base), …)` and falls back to the CPU for the fp64 maths,
because the B70 has no fp64. A graph captures the host pointer, so replay reads
freed memory.

That file is byte-identical in 112, so the blocker stands. The only known fix is
to precompute and keep the tables, which is a cache. The lane retired that kind
of memoisation under the no-caching rule.

The 2026-10-07 clarification in `notes/2026-10-06-resolution-cost-probe.md`
also records that the qualified pipelines kept `LTXVAEGraphGate` in `original`
mode, so it was never in use.

Enabling it on the chain would fail capture inside qualification. At best the
capture proof refuses and the server latches. At worst it repeats the 09-15
capture-abort fault class. So it does not fit the chain safely, and 113 ships
lever 1 alone. No decoder graph signature or pool is added. xpu:3 stays at
112's ~14.7 GiB free before a chunk and ~13.1 GiB after the decode peak.

If the owner allows a bounded, keyed, device-resident RoPE-table cache, decode
capture becomes testable. The 112 gate's eager/graph/repeat comparison would
then test it properly: the eager chain decodes eagerly and the graph chains
decode with the captured decoder. The prize is a share of the 0.95 s decode.
The 09-15 sampler experience suggests up to about half of it, but that is not
measured for this decoder.

## Coordinator addition: chain reset and border diagnostic

- **Reset.** A stream chunk with `reset: 1` (`stream_seq > 0`) is the stream_seq 0
  graph form plus one optional `reset` input on the output node.
  - It is unanchored, encodes its prompt fresh, and takes the next `stream_seq`.
    The chain restarts from its anchor.
  - The predecessor hash is recorded but not required: `""` or the current
    anchor. A wrong hash is refused (409, no latch).
  - Graphs without a reset are byte-identical to 112's, which keeps all
    qualification pins.
  - Qualification already covers the form: chunk 0 of every chain is
    unanchored and gate-less in the repeat chain.
  - Client options, both default off: `--reset-every-chunks N` and
    `--reset-on-scene-change`.
- **Diagnostic.** `anchor_diagnostics` in each receipt is computed from the F32
  anchor frame in float64:
  - the mean chroma (max−min of RGB), mean luma and clipped fraction of the
    outer 16-pixel ring and of the middle half square;
  - `border_to_centre_chroma_ratio`.

  It costs well under a millisecond. It is diagnostic only. A stdlib reference
  implementation in `stream_receipts.py` is tested against the torch one.

## What cannot be verified on CPU

- The real saving, and whether the concurrent MP4 encode slows the next chunk.
  The lane is CPU-dispatch-bound (`ltx-clip-is-cpu-dispatch-bound`). PyAV and
  the uint8 conversion mostly run outside the GIL, but contention could eat part
  of the 0.2 s. Watch the sampler-A and text-prep times in the first receipts.
- That `get_save_image_path` predicts the same `preview_00001_.mp4` path
  ComfyUI's own save would choose. It is the same function, called on a fresh
  per-chunk folder, and the receipt path is then enforced by an exclusive
  hard-link.
- That the PyAV mp4 muxer writes the same bytes under a `.partial` name. The
  container format is given explicitly, so the extension is not used.
- That ComfyUI's validator accepts the optional `reset` input. A test checks
  every emitted input against the node declarations.

## Risks

- **Shutdown during a write.** A SIGINT while a preview is queued can leave one
  chunk without a record and with a `.partial` file. Its receipt and anchor
  stay valid, and the CONTRACT says so.
- **Storage margin.** At build time there were 54.19 GiB free against a
  53.0 GiB requirement. The live 112 stream still consumes space; re-check
  after stopping it.
- **Reset visibility.** A reset chunk does not continue the picture. The owner
  should judge where resets look acceptable; scene changes are the natural
  place.

## Open questions

1. Decoder capture needs a RoPE-table cache. Allow a bounded, device-resident
   one as a separately qualified lever, or keep decode eager?
2. Client poll gap: 0.41 s per chunk on the live 112 lane is the `--poll 0.5`
   interval. Run the 113 client with `--poll 0.05`? This is client-only and
   likely worth more than lever 1.
3. `LTX_STREAM_TEXT_REUSE`: still 0, unchanged; the owner's ruling is pending.
   Its qualification path is intact.
4. Reset policy defaults for the live stream, if any. Both are off.

Sources:
- `recovery/20261008-continuation113-stream/` (code, tests, CONTRACT.md,
  LAUNCH.md)
- `data/resume-20261008/continuation113-build.json`
- `data/resume-20261008/continuation113-startup-check.json`
- `stream/ltx_continuation_client.py`, `stream/tests/run_tests_113.py`,
  `stream/tests/fake_comfy113.py`
