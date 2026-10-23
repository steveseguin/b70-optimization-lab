# Saved conversations (1.3.0)

The development build can keep complete client exchanges, including the newest
reply, and export them after a restart. This is **text-based resume**, independent
of the experimental runtime checkpoint work. PyPI 1.2.0 does not include it.

## Start saving

```bash
python3 ctxkeeper.py --recipe agent --upstream http://127.0.0.1:8000 \
  --state-dir "$HOME/.local/share/ctxkeeper" --save-conversations
```

Continue sending the full conversation to `/v1/chat/completions`. Give different
conversations different `X-Ctx-Session` headers, such as `project-a`. Names accept
1–64 letters, digits, dots, underscores and hyphens; `.` and `..` are invalid.
Without the header, the existing automatic key groups requests by their model
and opening messages. Explicit names avoid collisions between similar openings.
Names group snapshots; they do not erase previous branches or edited requests.

Saving is off by default. When enabled, `conversations.sqlite3` in the state
directory holds:

- Each complete incoming request, committed before model calls start.
- Each main request actually sent upstream, including recall and retry rounds,
  with its response when one arrived. Notes/prewarm calls are not included.
- The final response selected for the client and a diagnostic keeper-state
  snapshot after generation completes.

Identical message objects are stored once, while every snapshot preserves their
order and repetitions. Old snapshots have no automatic expiration. Storage still
grows with conversation content and successive view manifests. This includes
reasoning fields, tool arguments/results and embedded media sent in the JSON.
An image URL is preserved as a URL; the external image is not downloaded.

The database is unencrypted and newly created with owner-only file permissions.
Keep its directory private. For a consistent backup of the database **and** the
archive/notes files, stop the proxy before copying the entire state directory.
One proxy process should own a state directory; separate HTTP threads within it
are supported. The journal does not make the existing keeper files safe for
multiple proxy processes sharing that directory.

## Find and export

These commands run locally without starting a server or contacting a model:

```bash
python3 ctxkeeper.py --state-dir "$HOME/.local/share/ctxkeeper" --sessions list
python3 ctxkeeper.py --state-dir "$HOME/.local/share/ctxkeeper" \
  --sessions list --session project-a
python3 ctxkeeper.py --state-dir "$HOME/.local/share/ctxkeeper" \
  --sessions export --session project-a > saved.json
# Add --turn NUMBER to export an earlier snapshot.
```

The export contains the original `request`, final `response`, all `main_calls`,
diagnostic `keeper_state`, and a `continuation` when a completed assistant reply
exists. The continuation has the saved request body with that assistant message
appended, the session header, and `pending_tool_calls`.

Append the next user message before sending a continuation. If there are pending
tool calls, reconcile them with the client's execution records and supply their
matching tool results first. **Export never executes tools.** Do not blindly
rerun a command just because its result was not yet sent to ctxkeeper.

A minimal continuation for a completed text reply, using only Python's standard
library (with the proxy running at its normal address):

```python
import json
import urllib.request

with open("saved.json") as source:
    saved = json.load(source)
continuation = saved["continuation"]
if continuation is None or continuation["pending_tool_calls"]:
    raise SystemExit("Resolve the unfinished request or tool calls before continuing.")
body = continuation["body"]
body["messages"].append({"role": "user", "content": "Continue where we left off."})
body["stream"] = False
body.pop("stream_options", None)
request = urllib.request.Request(
    "http://127.0.0.1:18200/v1/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json", **continuation["headers"]},
)
with urllib.request.urlopen(request, timeout=1800) as response:
    print(json.load(response))
```

Use the same state directory to retain the current notes and recall archive.
The exported full history can also rebuild a new keeper's notes from text;
that requires model work. When branching from an older export, change the
continuation's `X-Ctx-Session` header to a new name: reusing the original name may
trigger the keeper's history-mismatch reset and set aside its current archive.
The diagnostic `keeper_state` is not imported:
it is not a self-contained checkpoint of archive files or asynchronous jobs.

## Failure semantics

`pending` means the input was committed but generation never reached its final
commit. `failed` records an exception; `complete` means the selected response was
committed before HTTP delivery. It does **not** prove the client received it.
A process interruption may leave a pending turn indefinitely. Exports select
the latest turn, including a pending/failed one, rather than silently choosing
an older successful reply. Select an earlier turn explicitly when appropriate.

If saving fails, the request fails instead of claiming it was saved. A failure
after an upstream call may mean the model generated an answer that was not
delivered; no tools are executed by the journal. Completed JSON records are
transactional, and exports verify stored object hashes. These hashes detect
accidental damage, not malicious database modification.

## Boundary with runtime checkpoints

The other host owns the [runtime checkpoint contract](../../experiments/own-xpu-runtime/SESSION-SWAP-DESIGN.md).
Its save/inspect/restore/delete operations remain experimental. This journal
neither calls those operations nor stores GPU tensors.

The [packet179 interface review](CHECKPOINT-INTEGRATION.md) records the concrete
CLI and gaps found in the first implementation. Its current restore path resumes
the same unfinished generation; general appended conversation turns still need
an engine operation and qualification.

The integration will need a runtime-issued checkpoint identity and the exact
rendered token prefix. A JSON message hash is **not** a token-prefix hash: chat
templates, tools, model identity and tokenization affect the actual prompt.
The runtime must verify compatibility and prefix equality before restoration.
Normal text processing remains the fallback after a checkpoint miss or a notes
edit. ctxkeeper will keep its existing note-placement policy; it will not append
changed notes to stale context merely to manufacture a cache hit.

Before connecting live operations, the runtime side must specify transport,
checkpoint lifecycle, tokenizer/template identity and a capability/qualification
signal. Its first design targets a 4,096-token TP1 configuration. That does not
qualify the 32K ctxkeeper configuration or any restoration speed claim.

The parking policy that will sit between this journal and those operations is
written and CPU-tested as `parking.py` (see CHECKPOINT-INTEGRATION.md, piece 3);
the request path does not call it yet.

This implementation is covered by CPU/scripted-model tests, including restart,
failure, concurrent sessions, tool calls and multimodal JSON. No GPU restore or
new model-quality/performance benchmark is claimed.
