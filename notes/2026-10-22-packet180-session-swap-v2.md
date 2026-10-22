# 2026-10-22: packet180 session checkpoint v2 prepared on CPU (append, restore-then-save, one manifest, shared lock, inspect modes)

## What and why

packet179 passed the device gate for **same-generation save/restart/resume** only. The ctxkeeper
source review ([CHECKPOINT-INTEGRATION.md](../tools/ctxkeeper/CHECKPOINT-INTEGRATION.md)) listed
five gaps before an integrator can use checkpoints for conversations: new turns cannot be
appended, a restored session cannot be saved again, the TSV and JSON metadata are not
cross-checked, restore and delete are not atomic against each other, and inspect has one costly
JSON-lines mode. [packet180](../experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/README.md)
closes all five in the engine's entry TU (no kernel change; all 41 kernel objects relinked
byte-identical from packet165, exactly as packet179). The manifest label stays `experimental`.

- Binary `f68714ce06c6318a6c7e9ea0b3aa39a58da684f872d6c10efe5f93b7ba143814` (two builds from the
  same source gave the same hash). Delta: main.cpp +70/−22 lines vs packet179 (+87/−6 vs
  packet165); checkpoint.hpp rewritten (306 → 919 lines: strict JSON reader, rendered-TSV
  cross-check, sibling flock, append/resume classification, pre-load precheck, inspect/delete).
- Append rule for integrators: `--input` = saved processed history + the pending token + the new
  turn. Same-generation resume (`--input` = the recorded prompt) is unchanged.
- Tokenizer/template identity: `one-card/tokenizer-identity.tsv` carries pins the harness already
  held (GGUF shard-1 header `7c1460a9…` incl. the chat template, tokenizer.py `1c284c06…`,
  vocab table `7a0e6124…`); save records it, restore refuses a different file.

## CPU results (no GPU, no device binary run beyond the sanctioned `--help`)

- Host-only C++ sessions (`checkpoint-probe.json`, 59 runs): append output equals a fresh
  reference of the same input; a restore-then-save chain of two restores equals the reference;
  the repeat append and a fresh one-shot save of the same history hold **byte-identical saved
  state blobs** (KV, GDN, PLE, controls), i.e. stepping a token as prefill or as decode leaves the
  same state on the CPU path; 26 refusal/boundary cases, every refusal before the upload marker
  and most before the model load (incl. the six from packet179, append prefix/pending/length,
  tokenizer mismatch, TSV-only `history0` edit, JSON history edit, extra file, never-overwrite,
  held lock, resume after a stop token, resume beyond the context); 10 delete cases incl. wrong targets
  (no lock file created) and a real concurrent delete-vs-restore (`in_use`; restore stays exact).
- packet179's real 128-blob device checkpoint, converted to the new manifest, passes this
  packet's C++ reader (metadata and full inspect, real control-blob cross-checks) — the semantic
  checks have been run on real device data before any window.
- Every analyzer the rows use was replayed on packet179's real receipts
  (`p179-receipt-replay.json`): packet179's checkpoint analyzer reproduces its own receipt, the
  row-a identity gate passes on the real outputs, and the full512 report reproduces 31.85 tok/s.
- The lifecycle worker arm ran at production shape (87-token prompt, K=256, 126-token turn,
  469-token NEW, 128-blob manifests) with mocked native launches; deliberate mismatches fail with
  the first divergent index and both streams saved (`lifecycle-test.json`).

## Device rows (proposal only, `ops/lane-queue/proposed-p180-one-card-A.txt`; not queued)

| Row | Estimate | Gate |
| --- | --- | --- |
| `packet180-one-card-full512-A-a` | ~8–9 min | full512 suite; every output equals packet179 row a |
| `packet180-one-card-lifecycle-A-b` | ~21 min (5 loads) | save S1 (K=256) → restore + append T (126 tokens) + 128 + save S2 → resume S2 + 64 → fresh reference of P+gen+T (192) → repeat append into S2b; (2) == ref[0:128], (3) == ref[128:192], (5) == (2), S2b state == S2, save == packet179 [0:256]; inspect/delete tools |

Admission is packet179's (lane A whole-host, fault review, 98.99 GB host memory, 25 GB floors,
7200 s watchdog); planned writes 400 MB. If the append path is not byte-identical on the real
model, row b fails and keeps the first divergent index and both streams.

- An independent read-only review of the native delta found nothing must-fix; its six
  should-fix items (resume context bound, pre-load tokenizer check, no same-generation resume
  after a stop token, resume first-token time, decode time excluding the save, failed-save
  cleanup) and the useful nits were applied, then every gate was re-run.

## Packaging state

Seal (547 files) → proposal → flags → live planner + rehearsal on a private copy →
`final_checks.py` → `final_checks.py --ready`. With READY written, the real pin guard on the full
closure: 613 pins = 605 in-packet + 7 packet49 oracle-binding targets + 1 own proposal; **0
cross-packet mutable pins**, both rows. Live planner after READY
(`lanequeue.py plan --lane A --directory …/evidence/queue-plan-one-card-A`):

```
{"name": "packet180-one-card-full512-A-a", "plan": "passed", "storage_admission": {"planned_write_bytes": 400000000, "root_free_bytes": 37441568768, "required_free_bytes": 25400000000, "passed": true}, "host_required_available_bytes": 98990252032}
{"name": "packet180-one-card-lifecycle-A-b", "plan": "passed", "storage_admission": {"planned_write_bytes": 400000000, "root_free_bytes": 37441564672, "required_free_bytes": 25400000000, "passed": true}, "host_required_available_bytes": 98990252032}
```

Rehearsal warnings are the same two packet179 had (no preparation-path probe declared; 14
unclassified gate-identity uses). Commit note: seven sealed files under
`one-card/lineage/packet179-receipts/row-b/run/checkpoints/gate/*.bin` (and the probe's run
blobs) match the repository's `*.bin` ignore rule and must be added with `git add -f`, as
packet179's blobs were; otherwise a fresh checkout fails the seal.

## Not claimed

No device result, no arithmetic or performance qualification; mini-geometry CPU equivalence
only. Label unchanged. Nothing committed or queued by this work.
