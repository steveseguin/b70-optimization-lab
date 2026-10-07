# Same-size optimized output gate

CPU-only, read-only evidence verification apart from one exclusively created,
fsynced receipt. No endpoint calls, model imports, replay, source edits or answer
repair. This component is not a launcher or setup admission gate.

## API and evidence layout

```python
verify_outputs(root, plan_path, reference_receipt_path, reference_sha256,
               phase, output_path,
               candidate_receipt_path=None, candidate_sha256=None)
verify_candidate_receipt(path, expected_sha256)
```

Paths are absolute, regular, nonsymlink evidence paths under the same constraints
as `reference_gate.py`. `phase` is `candidate-check` or `timed`. Candidate mode
requires exactly the frozen six requests / three emissions. Timing mode requires
exactly the frozen thirteen requests / ten emissions and a reconstructed verified
candidate receipt. The semantic plan SHA remains
`3281a1eb45d210ac75f2a07c415cf2f99b2b9308651456587aa483e2596d65e2`.

The native gate is reused without weakening: `verify_receipt` reconstructs all
six independent native requests, runtime identity, phase observations and complete
four-tensor finite byte inventories. The first three native captures remain the
only output oracle. The candidate evidence root must equal that native root;
server directory and source/model/process identity come from its bound runtime
contract, not from an untrusted candidate-supplied path.

For every frozen request, preserve exactly:

- `root/requests/NAME/prompt.json`, `submission.json`, `history.json`,
  `result.json`, `identity.json`, `events.jsonl`, in the native verifier's schema.
- Server receipts `pipeline-NAME.json`, `pipeline-sampler-NAME.json`,
  `pipeline-decode-NAME.json` from actual nodes. Each binds the session phase,
  plan, request, runtime, server, reference receipt and (for timing) candidate
  receipt. Full pipeline graphs, source identities, unique prompt IDs, successful
  uncached node events and ordered start/success timestamps are checked.
- For emitted clips only, `root/output/validation/NAME/summary.json` and
  `tensors.safetensors`, plus server `pipeline-save-NAME.json` and the three
  `pipeline-done-{sample,decode,save}-ABSOLUTE_INDEX.json` markers.
- The successfully saved preview path recorded in the save marker, under
  `root/output/`; its bytes are bound for delivery evidence, never pixel parity.

The module follows immutable99b `pipeline_decode_node.py:504–612,618–648` and
`run-throughput-fixtures-98.py:334–383`: node414 captures the tensors emitted by
node426 **under the current emitting request name**. The preview writer receives
CPU image/audio copies and saves only MP4; it does not supply a later raw tensor
archive. The first three node414 captures may contain small fill placeholders and
are deliberately never read or counted as tensor comparisons. Raw evidence is
never rewritten by this gate.

## Clip and preview mapping

Sampler W1/depth1 emits the prior submitted absolute index (first request emits
-1). Decoder depth2 emits another two requests behind. The gate checks these
separate absolute indices against the fixed stream base and the plan's relative
emitted index, including all three fills. Emitted indices must be exactly0..2
or0..9, in request order, with no duplicates or substitutions. The frozen fixture
and native-reference name are looked up from each plan row, not from a worker's
claim. All four archive tensors must have exact expected F32 shape, finite values,
metadata matching actual bytes, and hashes equal to the native reference.

The decode job for relative clip j was enqueued by request j+1; its preview prefix
is therefore `rows[j+1].name + '/preview'`. The emitting request j+3 has a v2 save
record naming that earlier prefix. Sample/decode/save completion markers must
match the actual absolute emitted index and session identities. Sample must be
finite, decoder slot must be native for even absolute indices and replica for odd indices, save must identify an existing
preview rather than `save-failed:*`, and completion times must be ordered. This preserves the pinned deterministic native/replica placement rule; both
placements must match the same native output bytes. Decode completion precedes the emitting success event;
preview completion may follow it and is checked separately before receipt.

## Receipt and authority boundary

Candidate receipt status is `candidate_verified`; timed receipt status is
`timed_verified`. Both state three distinct fixtures and three unscored fills.
`verify_candidate_receipt` checks the expected receipt digest and reconstructs the
entire proof before returning the plan/runtime/server/reference SHA fields needed
by `session.Authority.advance`. A coherently rehashed receipt cannot substitute
for missing/changed raw evidence.

Timing reports the nine server-success intervals between ten emitted clips,
cycling three fixtures. These are generated clip completion intervals, not playback
FPS. Preview completion is checked separately and not silently folded into that
metric. Neither receipt claims general video quality, unseen prompts, longer
videos, other resolutions or a speed record.

Setup acceptance is separate: the trusted executor adapter must require passed
actual graph coverage/chain/freeze/replica receipts before these requests. This
gate does not reinterpret a successful setup UI history as a passed setup test.
Native-reference OOM/eviction protection, memory/disk budgets, pending-tail
retirement, source sealing and graceful shutdown remain launcher/coordinator
obligations. Runtime integration and GPU qualification are still pending.

## Offline controls

```bash
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_candidate_gate.py
```

Sixteen controls use the actual frozen plan and real schemas with tiny synthetic
F32 archives. Only tensor dimensions/model identity are patched through the native
gate's existing fixture helper; verification functions are not mocked. They cover
full candidate/reconstruction/timing, fill exclusion, wrong emitted index, missing
worker marker, wrong deterministic decoder slot, failed preview, coherently changed tensor bytes, source/graph/phase
changes, cached/missing node execution, exclusive output, forged rehashed receipt,
fault/permanent-session-halt refusal and timing without a candidate receipt. No GPU/model calls occur.
