# Existing MTP compatibility and CPU bridge

This is an additive CPU check for the downloaded SC117 GSQ-RCO abliterated
IQ3_S target. It does not load weights, create a model owner, use a device,
download anything, or implement a new inference server.

Our existing two-card runtime already supports one-token MTP. The published
P196 one-card record is target-only. The P198/P201 single-owner streaming front
explicitly rejects MTP; enabling a flag there is not a serving integration.

The existing draft can be reused from the local official FP8 model. Its 3,101
tensor entries cover 2,698,026,496 bytes in 28 safetensor files under
`/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`. These are regular local files,
not links into the excluded RAID. The receipt checks size, device, inode and
nanosecond modification/change times against the existing authenticated
manifest. It reads no tensor payload and makes no new payload-hash claim.
The exact tensor names, offsets, BF16/F8_E4M3 types, rows, columns and historical
hashes are preserved in [draft-manifest.tsv](draft-manifest.tsv).

The draft loader retains BF16 dense weights, converts offset norms to F32
`1+w`, and requantizes FP8 routed experts to signed INT8 with F32 scales per
16 values. This is draft-only quantization. The target embedding and head
remain the target's own weights. The linked 4,137,470,112-byte SC117 Q8 GGUF
draft is neither required nor compatible with this loader without another
adapter. Its card says the draft is stock, not abliterated. No need to download
it merely to obtain an MTP implementation.

## What is tested

[source-audit.json](source-audit.json) binds the inherited implementations.
[bridge.py](bridge.py) imports the exact P195 `pipeline.Controller`, the
existing `test_state_machine.Mock` target transitions, and the actual
`Transport.draft_result` packed-publication validator. It does not reimplement
their accept/rollback logic. The provider returns injected proposals derived
from the synthetic target-only control, with forced incorrect, missing,
out-of-range, stale-position, stale-sequence and error variants.

The assertions compare complete synthetic histories, recurrent rows, committed
fixtures and emitted tokens against the target-only control. They check:

- DRAFT receives `H_(p-1)` and confirmed `x_p`, at draft position `p-1`.
- Proposal hits and misses do not change the confirmed draft-input sequence.
- Rejection restores target state; only target-verified tokens are emitted.
- A pre-append provider error disables drafting without adding a cache row;
  a post-append error retains that row and disables further draft work.
- Stale publications are ignored; transport exceptions propagate without retry.
- EOS discards pending target speculation. Tests also cross positions 31/32/33
  in the synthetic state machine; they do **not** test native capture resizing.

The provider append/disable behavior is a source-derived test double, not an
execution of `DraftRuntime`. The CPU target recurrence is the existing test
mock, not Qwen math. These tests do not establish native event ordering,
rollback-copy correctness, GPU teardown, neural draft acceptance or speed.
The real native controller, snapshot and draft implementation are source-bound
for reference; their previous qualification is not a new-model qualification.
Inherited controller timing/acceptance labels are deliberately excluded from
the promoted synthetic summaries.

[contract.py](contract.py) binds the sibling metadata census and requires every
architecture/PLE/tokenizer field to match the old target, including the full
canonical token/merge/template hashes. It checks 48 layers, hidden width 2560,
four hidden streams, 512 experts, vocabulary 248320, embedding/head shape and
distinct PLE EOS 248044 versus tokenizer EOS 248046. It does not equate the
embedding/head payloads merely because metadata matches. The new embedding
is IQ4_XS, which the frozen loader cannot decode yet. The full Q6_K target head
has unchanged shape/type. Old draft-prefix calibration at 80,128 rows is not
transferred; use an explicit full-vocabulary draft policy for first admission.

## Reproduce the CPU checks

From this directory, run the tests without changing any evidence:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
taskset -c 8-15,24-31 nice -n 19 python3 -B -c \
'import resource, unittest; resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3)); resource.setrlimit(resource.RLIMIT_CPU,(120,120)); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(".",pattern="test_*.py")); raise SystemExit(not r.wasSuccessful())'
```

[run_cpu.py](run_cpu.py) is the original one-shot evidence writer. It refuses
an existing `evidence/` directory, enforces the CPU/memory limits and prevents
network, subprocess, model-payload and device opens during the tests. Existing
receipts must be retained rather than overwritten. Total artifacts remain
well below the 50 MB budget. This code offers no device execution command.

## Remaining wiring

First implement and independently test exact SC117 tensor-format support,
especially IQ4_XS target embedding lookup and the changed expert formats.
Generate a new target plan/dispatch and host/device memory census; do not reuse
P195's sealed old-model plan. Then connect the new target's actual confirmed
hidden states to the existing private draft, beginning with a full draft head
and target-only comparison. A two-rank request front must also manage reset,
pending speculation and drain across both owners. A one-card MTP verifier is
a separate integration, with draft/cache costs; no speedup is presumed.

These CPU checks establish a compatible metadata interface and synthetic
controller behavior only. Native admission and new-model acceptance remain
false until those later gates pass. No old sealed files were modified.
