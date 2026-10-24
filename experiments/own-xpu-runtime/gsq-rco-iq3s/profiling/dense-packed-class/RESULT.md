# Historical BF16-state class diagnostic

The single fixed prompt00 target-only128 diagnostic passed independent token and
state readback against the historical5aef engine. One excluded8-token warmup and
one measured request ran in one persistent pair; all6 bundles and the five-stage
capture budget closed. Physical device contact, graceful drain, unchanged protected
vision process and the existing fault baseline were checked.

The measured request consumed214 positions. Summed device class events across
both ranks total10,249.070221ms; this is neither request wall time nor decode-only
time. Expert down/gate/up sum1,093.830/935.249/922.951ms; routing700.882ms,
GDN recurrence377.482ms. No model-speed claim follows from these class totals.

Further speed changes are held because this engine rounds recurrent matrix state
to BF16 each token. Internal exactness does not establish reference-F32 fidelity.
The immediate work is the additive recurrent precision correction and independent
same-weight reference comparison, not another class optimization.

[Independent actual review](evidence/device-a/review.json) and
[closed artifact index](evidence/device-a/artifact-index.jsonl.gz) retain the
measurements. The plan-display KeyError was a summary-printer failure after a
successful saved plan, not a device failure; see
[evidence note](evidence/plan-display-note.json).
