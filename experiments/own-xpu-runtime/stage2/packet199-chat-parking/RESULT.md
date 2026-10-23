# Real HTTP chat with exact parked-session continuation

## Question and identity

Can real text chat use the native owner, pinned tokenizer/template, checkpoint
adapter, store and bounded parking policy without changing model output?
This pilot uses one unchanged packet198 device binary on card 0, Qwen3.8
Flash-Next Unsloth UD-IQ3_XXS, target-only greedy decoding, context 4096,
full BF16 KV/state and the baseline 21,552,729,600-byte expert cache.
[Readiness](READY-FOR-DEVICE.json) pins 215 source and 35 dependency files.
This identity is separate from the max23 expert-diet cold record.

## Outcome

All six real loopback HTTP requests passed: 896 generated tokens, five SAVE
controls, one RELEASE and a clean six-request/six-control stop. One process
(PID 3431024) loaded the model once and remained on card 0. There was no new
kernel fault, incident signal or retained child. The independent audit passed.

| Request | Prompt tokens | Output tokens | Verified behavior |
| --- | ---: | ---: | --- |
| A park |87|256|Exact retained p198 A output; save complete history.|
| B park |60|128|Exact retained p198 B output; save.|
| A chat append |370|128|Restore342 processed tokens plus pending token; append27 rendered tokens.|
| Fresh chat reference |370|128|Exact append output and all129 saved blob digests.|
| Edited A |394|128|Changed prefix selects fresh processing.|
| Final B without parking |60|128|Exact B repeat; release normally before owner stops.|

The controller independently confirmed passive device drain and began the
single restore28 application restoration at 18:08:16 UTC. All three applications
validated by 18:17:48 UTC. Both worker and controller exited successfully; original
lane pauses remain intact, both queues are empty and STOP latches are absent.

## What worked

The actual HTTP layer, codec, chat facade, adapter, native store and parking
policy ran together. HTTP request IDs bind to native results, complete text,
finish reasons and usage. The caller's real continuation messages render an
exact 343-token saved prefix followed by 27 new tokens. The old p198 raw-token
append is not used as an oracle for this different chat input.

Both the append and fresh run generated the same 128 IDs and saved the same 129
blob digests. The edited initial message caused a prefix miss. Parking enforced
its 512 MiB budget using the proven 256 MiB peak reservation per checkpoint and
performed three native policy deletions. The zero-budget final service shared
the same owner and released its completed reply without saving.

The independent audit rehashed all 258 surviving blobs (147,009,584 bytes).
Every SAVE's captured manifest, small control payloads and full visible history
were independently validated. The closed worker evidence inventory contains
100 files totaling 4,555,865 bytes, with exact checksums.

## What failed or remains uncertain

No device request failed. All replies reached their requested token caps and
correctly report `length`; this run does not qualify natural stopping. The
edited prompt has no prerecorded output oracle: its native consistency,
prefill choice and HTTP mapping passed, without a new quality claim.

Three checkpoints were deleted by the admitted parking policy. Their full
blob maps were captured and checked against manifests by the sealed worker
before deletion; those deleted raw tensors cannot be independently rehashed
later. Both surviving raw states remain locally under `evidence/runcheckpoints`;
the audit records their identities, sizes and hashes. No raw model or large
checkpoint tensor is committed to Git.

This is a bounded six-request functional pilot. It does not qualify general
serving, streaming, concurrency, authenticated session isolation, restart
recovery, long context, cold speed or a LocalMaxxing record. The native receipt's
experimental `real_model_qualified=false` remains unchanged. Parsed protocol
fields and native SAVE receipts are retained; there is no independent raw
stdout transcript.

## Evidence and patches

- [Independent restoration audit](evidence/independent-restore28-review.json) and
  [copied application validation](../../ops/packet199-window/evidence/window-a/endpoint-restoration/copy-receipt.json).
- [Independent device audit](evidence/independent-device-result.json),
  [worker result](evidence/device-p199-chat-A-a/worker.json),
  [HTTP rows](evidence/device-p199-chat-A-a/http-requests.json),
  [guarded operations](evidence/device-p199-chat-A-a/guard-operations.jsonl).
- [Compact inventory](evidence/closeout-inventory.json),
  [native shutdown](evidence/device-p199-chat-A-a/owner/receipt.json),
  [reviewed controller](../../ops/packet199-window/README.md).
- [Auditor source](../../integration/audit_p199_result.py),
  [tamper/refusal tests](../../integration/test_audit_p199_result.py).

## When to revisit

The next step is an additive bounded session lifecycle for the same attached
owner: interactive sequential requests, explicit request/idle/deadline limits,
intake closure before one normal owner close, and no retry or replacement.
CPU tests and independent review precede any separate live qualification.
Streaming follows that lifecycle seam. Longer context requires a new device
capacity census and SAVE-size proof; the 4096 bound does not cover 8192.
