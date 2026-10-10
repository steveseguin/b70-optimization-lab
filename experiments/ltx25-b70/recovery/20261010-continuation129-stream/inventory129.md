# Packet 129 HTTP evidence inventory

Scope: packet 128's sealed server, its admitted stream graph and packet 129's
publication changes. No live route, model or existing run was opened for this
audit. References below are source names and symbols inside the packet.

| Route / consumer | Files or state read | Packet 128 writer | Packet 129 publication |
| --- | --- | --- | --- |
| `GET /ltx-stream/receipt/{run_name}` | `run/receipts/receipt-<name>.json` | `session.StreamAuthority.finish` calls `session.write_exclusive`: final-name exclusive open, write, fsync | Same canonical bytes/hash; private same-directory file, fsync, exclusive rename, directory fsync |
| `GET /ltx-stream/decode/{run_name}` | `run/receipts/decode-<name>.json` | `integration.Runtime._decode_job` calls `Runtime.write`, then the same direct session writer | Same atomic session writer; unchanged strict `read_regular` guard |
| `GET /ltx-stream/preview/{run_name}` | `run/receipts/preview-<name>.json` | `Runtime._commit_preview` calls packet 123's `stream_preview.write_record_atomic` | Existing packet123 helper retained byte-for-byte, with canonical bytes and exclusive rename |
| `GET /view` | `output/<chunk>/preview_00001_.mp4` | Packet 123 `stream_preview.save_preview_atomic`: completed temporary MP4, fsync, `renameat2(RENAME_NOREPLACE)`, directory fsync | Retained; `.name.partial` paths denied by `/view`, including asset-hash and symlink aliases |
| `GET /view` | `output/validation/<name>/tensors.safetensors` | `capture_node.LTXBaselineCapture.capture` calls `save_file` on final name | Same serializer/tensors; write private same-directory file, fsync, exclusive rename, directory fsync |
| `GET /view` | `output/validation/<name>/summary.json` | Same capture method calls final-name `write_text` | Identical indented JSON bytes through atomic publication helper |
| `GET /ltx-stream/status` | Locked in-memory authority, decoder, preview, maintenance and storage snapshots; file-existence checks only for `ROOT/FAULT.json` and `run/stream-halt.json` | Halt via session writer; fault via launcher's `write_json` | Both JSON producers atomic; status does not parse either file and cannot expose its partial payload |
| `GET /ltx-encoder/identity` | Immutable object parsed from `run/server-identity.json` before listener installation; import-time SHA and PID checks | `launch/serve-encoder.py:write_json` directly opens final path | Startup writer atomic; identity route still serves its checked in-memory snapshot |
| `POST /ltx-stream/action` (`qualify-verdict`) | Committed receipt/decode JSON, qualification `tensors.safetensors`, sealed reference hash JSON | Listed receipt/decode/capture writers; packet builder writes reference before seal | Atomic artifacts above; action still drains both workers and requires their committed records before reading; reference remains sealed immutable |
| Same action's returned evidence | `run/stream-qualification-verdict.json`, `run/stream-freeze.json` | `Runtime.write` / session direct writer | Atomic session writer; action returns only after publication |
| `POST /prompt` admission / predecessor proof | Sealed `resolution/stream-plan.json`, frame/latent/guide anchor files, committed predecessor decode records and their declared hashes | Plan prepared before seal; `stream_receipts.write_anchor` and `latent_anchor.write_anchor` write anchor final paths directly | Plan immutable; both anchor producers atomic; same finite-value, shape, hash and identity checks |
| `POST /prompt` inherited fault middleware | External `ROOT/model-verification.json`; existence of `ROOT/FAULT.json` | External preparation scripts, detailed below | Fresh status check retained; verification gate atomically replaces whole versions; fault writer atomic |

The session primitive also covers stream-before/after records, safety receipts,
failure records, installation/preparation records, latches and other run JSON.
These are not independent file-serving routes, but changing their shared writer
prevents another direct-write hole when an existing consumer reads them.

The generic `/view` route serves the configured output and temporary trees. For
the admitted stream graph the generated evidence files there are the MP4,
qualification safetensors and summary listed above. Input assets, model metadata
and the server's static UI are pre-existing inputs, not growing run evidence.
Inherited pipeline-node diagnostic JSON lives in the run directory outside the
output tree; no HTTP handler reads it. `text-window-probe-*.json` is consumed by
the completed prompt worker, rather than directly by a route.

The sealed packet manifest, plan, references and source files are complete before
the launcher accepts the manifest. Their build-time writes cannot overlap live
HTTP reads. No route reads an append-only evidence manifest. `host-stalls.jsonl`,
server logs and journal snapshots are operational diagnostics, not HTTP evidence
inputs. Consequently no committed-prefix parser is needed and no trailing
partial line is treated as a committed record.

## External model-verification producers

`experiments/ltx25-b70/scripts/finalize-model-verification.py` writes
`model-verification.tmp`, flushes and fsyncs it, replaces the final pathname, then
fsyncs the directory. It refuses to replace an already-passed gate. This is an
existing complete-version publication path. The middleware reads the open file
once and therefore sees the old or new complete version during a rename; it does
not run the stream evidence path-identity guard on this external mutable gate.

The earlier preparation script `experiments/ltx25-b70/scripts/stage-model.py`
also writes a same-directory `.tmp` and replaces the final gate after each
staging update. In packet 128's repository state its `save` helper lacks file
and directory fsync. This already prevents a half-written HTTP response, but
does not provide the requested durability guarantee after a power failure.
Packet 129 adds flush/file-fsync before its existing replace and directory-fsync
after it, preserving its exact JSON bytes and replacement semantics. Its actual
`save` function is AST-extracted for a CPU race test against the actual prompt
middleware; neither script top-level nor model staging is executed. That helper
is not part of the runtime packet and must never be run
as a packet 129 validation step. Existing model weights and the live external
gate must remain untouched.

## Guard and race-test requirements

`read_regular` compares device, inode, size, mtime, ctime and link count from the
open descriptor before/after the read and from the final pathname. Its code is
unchanged. Replacing an existing final name is therefore insufficient: it can
change the old inode's ctime/link count while a reader holds it, or change the
pathname identity. Runtime evidence final names remain immutable and exclusive.
No hard-link/unlink publication is used. Duplicate publication refuses while
leaving committed bytes unchanged.

CPU tests execute the actual capture method with fake tensor math, the actual
extracted `/view` handler with real writer threads paused mid-write, the actual
identity and model-gate handlers, and the isolated launcher `write_json` function.
They open no listener and import no launcher or native runtime. All scratch is
owned by `TemporaryDirectory` and deleted by test cleanup. `/view` returns 404
for unpublished final names and guessed staging names; after publication its
file response points to complete identical bytes. The external model gate keeps
its inherited 503 refusal while the old complete version is pending, and admits
only after a complete passed version is committed. That 503 is an intentional
model-admission decision, not a torn-read failure.
