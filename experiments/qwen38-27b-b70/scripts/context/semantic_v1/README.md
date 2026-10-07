# Semantic development adapter, diagnostics and bounded live trials

This is a separate development tool, not a revision to the frozen r4 experiment.
The optional live client requires an already qualified local endpoint. There is
no model launcher, speed gate or holdout admission. The
ledger and bounded answer/retrieval protocol were copied from `durable_v4`; the
answer protocol now uses each question's explicit `answer_type`, including
integer historical answers.

`tasks.load_packet(documents_path, adjudicated_path)` checks the actual document
bytes against the adjudication hash and verifies the two independent annotation
source hashes. Annotation paths must remain inside the adjudication directory.
It requires exactly one annotation for every document and preserves the source
batch texts byte-for-byte within their JSON strings. `compile_document` accepts
the agreed canonical document/annotation contract; it does not infer events or
answers from prose. Ordered literal set/add/sub events are checked against exact
source substrings, then replayed solely to detect disagreement with the separately
supplied checkpoint states. Replay consistency does not establish semantic truth.

Compiled tasks contain private reference answers/events/states. Keep compiled
tasks on the host side. `public_task(task)` provides only original batches,
typed questions, document ID and the packet's reading conventions. It returns
a deep copy; `reference_view(task)` returns a read-only copy for host-side
scoring. Never serialize the compiled task or reference view into model prompts.
`diagnostics.answer_payload(task)` includes the typed answer instruction,
questions and reading conventions, with no reference answers. The live harness
preserves those conventions at ingestion and answering, and reveals public
questions only after all four batches have been processed.

The diagnostic evaluator accepts already recorded attempts for summary, archive
or quoted arms. It makes no calls and generates no retries. Its trace format is:

```json
{
  "document_id": "s01-stress",
  "arm": "quoted",
  "batches": [{"batch_id": 1, "attempts": [{"events": []}]}],
  "answers": {},
  "refusals": []
}
```

This abbreviated shape is not a complete valid trace: supply every source batch
and its actual recorded responses. Archive responses contain `state`; summary
responses contain `memory`. Original per-attempt event diagnostics and refusals
remain visible even if a later attempt succeeds. Transactional receipts come
from a temporary replay database and are labeled CPU replay, not original model
execution evidence. Summary's unobserved internal states remain unknown.

Semantic event matching compares counter/operation/amount. Valid differences in
quote span do not reduce semantic matching. Unmatched events with one unambiguous
identical gold quote are classified as substitutions, with wrong fields reported;
ambiguous leftovers remain omissions or spurious events rather than guessed
correspondences. Provenance/transaction acceptance is reported separately. All
checkpoint states and final answers are graded separately, so a later overwrite
cannot hide an earlier omitted posting. `compare_pairs` retains both complete
results and rejects missing/duplicate stress-control members.

## Optional live execution

`live.py --documents DOCUMENTS --annotations ADJUDICATED --out NEW_DIRECTORY`
prints the prospective plan without making requests. Add `--execute --endpoint
LOCAL_URL --model MODEL --identity LAUNCH_JSON` only for a qualified endpoint
under the host supervisor. The client never starts, restarts or stops a server.
`--stub` is a separate, explicit oracle wiring mode; it is not model evidence.
Every executed output directory must be new; there is no resume or replacement.

The fixed matrix contains twelve documents and three arms, sorted by document
ID, with arm order rotated by document index modulo three. All arms process all
four batches. Summary compresses after **each** batch: this is a short semantic
diagnostic, not r4's workload or a memory-window comparison. Prompts are bounded
to 32,768 serialized UTF-8 bytes and stored model memory to 6,553 bytes. Ingestion
uses thinking off and a 4,096-token output limit, with at most three JSON/protocol
attempts per batch. Answering uses medium reasoning and an 8,192-token combined
reasoning/output limit, at most 32 actions and 24 retrievals. No cap increases or
HTTP retries are performed.

Valid HTTP responses ending in length, filtering or another non-stop outcome,
and exhausted protocol budgets, produce a retained failed trial. The remaining
matrix continues. Malformed HTTP envelopes, transport/server errors and internal
ledger faults preserve available evidence and abort the campaign. An explicit
complete submission is required; typed wrong answers and null unknowns remain
incorrect even when submission is complete. Missing answers count wrong.

Native `trace.json` uses `semantic-live-attempt-trace.v1`: enriched attempts hold
responses, refusals, semantic metrics, observed state and original receipts. It
is intentionally distinct from the CPU replay input above. No missing replies
or unvisited batches are invented. Native results distinguish ingestion, final
submission and full protocol completion, bind raw calls/trace/checkpoint/session
artifacts with SHA256, and report absent cache usage as unknown. Raw calls retain
original response messages, reasoning and token/cache metadata. The plan binds
source code, document/annotation identity and runtime identity, rechecked around
each trial. Single-server timings remain descriptive; both speed and holdout
admission flags always remain false.

Run the CPU checks from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s experiments/qwen38-27b-b70/scripts/context/semantic_v1 -p 'test_*.py'
```

The complete-packet test deliberately replays the private reference events to
check adapter/ledger compatibility. It is an oracle wiring test, not a model
measurement. All tests use temporary databases; the authored documents and
independent annotation files are read-only.
