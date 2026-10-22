# Packet 180 — session checkpoint v2: append, restore-then-save, one manifest, shared lock, inspect modes

**Status: CPU-prepared, sealed, proposal written (not queued); device qualification pending.
Label stays `experimental`.** This packet closes the five integration gaps of
[CHECKPOINT-INTEGRATION.md](../../../../tools/ctxkeeper/CHECKPOINT-INTEGRATION.md) and
[SESSION-SWAP-DESIGN.md](../../SESSION-SWAP-DESIGN.md) §10 item 0 in the engine, on top of the
packet179 checkpoint (same-generation save/restart/resume, device gate passed 2026-10-22).

## What changed (entry TU only; arithmetic untouched)

| Item | Change |
| --- | --- |
| A. Append | `--checkpoint-restore ROOT --checkpoint-id ID --input NEW` where NEW = saved history + pending token + new tokens; the new tokens go through the normal prefill path, then normal decode |
| B. Restore-then-save | restore and save combine; the new checkpoint gets a **new** id (`--checkpoint-save-id`), never overwrites; a chain of restores is supported |
| C. One source of truth | `manifest.json` is parsed once by a strict JSON reader and is the only source of values; `fields.tsv` is rendered **from** the parsed manifest and must equal that rendering byte for byte |
| D. Shared atomic lock | sibling lock file `ROOT/ID.lock` (flock): shared for restore/inspect, exclusive for save/delete, never waits; delete validates its target first |
| E. Inspect | `--checkpoint-inspect DIR` verifies every blob and prints ONE JSON object; `--checkpoint-inspect-metadata DIR` reads only `manifest.json` + `fields.tsv` |
| F. Manifest | `label: "experimental"` (unchanged), new `contract: "v1.2+p180"`, `operations: ["same-generation-resume","append","restore-then-save"]`, `lineage`, `tokenizer_identity`, `geometry.qh` |

Native delta: `one-card/lineage/packet180-vs-packet179-main.patch` (main.cpp: +70/−22 lines vs
packet179), `packet180-vs-packet179-checkpoint.patch` (checkpoint.hpp rewritten, 306 → 919 lines),
`packet180-native-delta.patch` (main.cpp vs packet165: +87/−6). The authoritative header is
[`checkpoint.hpp`](checkpoint.hpp) at the packet root; `adapt_native.py` installs it.
Every kernel object (41) is relinked byte-identical from packet165 exactly as packet179 did.
Device binary `one-card/build/device/own-rt-iq3`:
**`f68714ce06c6318a6c7e9ea0b3aa39a58da684f872d6c10efe5f93b7ba143814`** (rebuilt twice from the
same source: identical). Arithmetic parent packet165 `1364bb3d…`; previous checkpoint engine
packet179 `8d185384…`.

## Operation semantics

Terms (all token ids):

- **P** — the `--input` of the process that wrote the checkpoint (its *recorded prompt*;
  `token_state.prompt_length = len(P)`).
- **processed history H** — every token the model stepped in that session, in order
  (`tokens.bin`, length `N = token_state.position = token_state.length`).
- **pending token t** — the last generated token: its argmax was computed but it was never
  stepped (`token_state.next_token`).
- **saved history** — `H + [t]`, length `N+1`: everything the caller has seen.

For a fresh `save` after decoding K tokens `g[0..K)` from P: `H = P + g[0:K-1]`, `t = g[K-1]`.
For a save after an append: `H = NEW + g'[0:M-1]`, `t = g'[M-1]`, recorded prompt = NEW.
For a save after a same-generation resume of a checkpoint (H, t): `H' = H + [t] + g'[0:M-1]`,
recorded prompt unchanged.

`--checkpoint-restore` chooses the operation from `--input` (refused otherwise, before any upload):

| `--input` | Operation | What runs |
| --- | --- | --- |
| exactly the recorded prompt (same length, same tokens) | **same-generation resume** | t is stepped as the first decode step at position N; output continues the interrupted generation |
| starts with H (N tokens), then `input[N] == t`, then a delta D (may be empty) | **append** | `input[N..]` (t first, then D) are stepped through the unchanged prefill path from position N, exactly as a fresh run of the same input steps those positions; the last input token's argmax is the first generated token |
| anything else | refused: `prefix` | names the first mismatching index, the pending-token mismatch, or the length rule |

Two more rules, both refusals before any upload: a same-generation resume is refused
(`ended generation`) when the pending token is a stop token (eos 248044, or 248046 on the full
model) — the uninterrupted run ended there, so stepping it would produce tokens that run never
produces; an append after a stop token is allowed (a chat turn follows an end-of-turn) and the
result records `pending_is_stop: true`. A same-generation resume must fit the context:
`N + --max-new <= context` (one less when the run also saves); an append needs
`len(NEW) + --max-new <= context`.

Append with an empty delta equals the same-generation resume (CPU-probed). The integrator's
rule: **NEW = H + [t] + new turn**, i.e. the full conversation the caller has seen, plus the
new tokens. Editing anything inside H invalidates the checkpoint (design §5).

## Exact CLI

```
# save (fresh run)
own-rt-iq3 <admitted args> --input P.txt --max-new K \
  --checkpoint-save ROOT --checkpoint-id ID --tokenizer-identity one-card/tokenizer-identity.tsv
# same-generation resume
own-rt-iq3 <admitted args> --input P.txt --max-new M \
  --checkpoint-restore ROOT --checkpoint-id ID --tokenizer-identity …
# append (and optionally restore-then-save into a NEW id)
own-rt-iq3 <admitted args> --input NEW.txt --max-new M \
  --checkpoint-restore ROOT --checkpoint-id ID [--checkpoint-save ROOT2 --checkpoint-save-id ID2] \
  --tokenizer-identity …
# device-free host tools (argc == 3; dispatched before argument parsing or any device/model access)
own-rt-iq3 --checkpoint-inspect ROOT/ID
own-rt-iq3 --checkpoint-inspect-metadata ROOT/ID
own-rt-iq3 --checkpoint-delete ROOT/ID
```

Argument rules (parse time): ids are 1–64 characters `[A-Za-z0-9._-]` starting with a letter
or digit; `--checkpoint-save-id` only with both restore and save, and `ROOT2/ID2 != ROOT/ID`;
`--tokenizer-identity` is required for every checkpoint mode and refused without one;
checkpoint modes are single-request and plain decode (no `--suite-inputs`, `--first-layer`,
`--bracket-inputs`); ids ending in `.lock` are refused (sibling lock names). **Before any model
load**: a save target that exists is refused (`never overwrite`); the tokenizer-identity file is
parsed; and a restore is pre-checked under the shared lock — manifest seal, `fields.tsv`
cross-check, closed file set, `tokens.bin` and token-history, tokenizer identity, and the
`--input` classification with the stop-token and context rules. Restore repeats every one of
these authoritatively under its lock after the model load, together with the engine-dependent
checks (binary sha256, geometry, model identity, completeness against the live plan, every blob's
sha256 and the control-blob cross-checks).

## On-disk format

```
ROOT/ID.lock            sibling lock (flock); created by save/restore/inspect, removed by delete
ROOT/ID/manifest.json   the only source of values (compact JSON, one line)
ROOT/ID/fields.tsv      derived index rendered from the parsed manifest (grep-friendly)
ROOT/ID/tokens.bin      H as int32 little-endian
ROOT/ID/<buffer>.bin    one per manifest blob (KV sliced to N rows, pooled to N/4; rest whole)
```

Nothing else may be in the directory (closed file set; an extra file such as packet179's
`restore.lock` is refused). `manifest.json` appears last (atomic rename after every blob,
`tokens.bin` and `fields.tsv` are fsynced), so a partial save is never visible; a save that fails
removes its partial directory while still holding the exclusive lock, so the id stays usable.

`manifest.json` (keys exactly; extra or missing keys are refused):

```
{"format":"ownrt.session-checkpoint.v1","label":"experimental","contract":"v1.2+p180",
 "operations":["same-generation-resume","append","restore-then-save"],
 "checkpoint_id":ID,"created":ISO8601,
 "lineage":{"operation":"save"|"restore-then-save","parent":null|{"checkpoint_id":…,"manifest_sha256":…}},
 "model":{"identity_tsv_sha256":…,"shard_stat_rows":[{name,size,dev,ino,mtime,ctime}×3]},
 "engine":{"binary_sha256":…,"packet":"packet180-session-swap-v2","profile":"tp1-full512"},
 "geometry":{"layers","qsa_layers":[…],"gdn_layers":[…],"kvh","ad","ih","id","qh","gdn":{"kh","vh","d"},"context","vocab","eos"},
 "dtypes":{"kv":"bf16","gdn_state":"bf16","ple":"bf16"},
 "tokenizer_identity":{"file_sha256","format":"ownrt.tokenizer-identity.v1","gguf_header_sha256","tokenizer_source_sha256","vocab_bin_sha256"},
 "token_state":{"prompt_length","length":N,"position":N,"next_token":t,"tokens_sha256","token_history":[H[N-2],H[N-1]]},
 "sampler":{"mode":"greedy-argmax","state":null},
 "blobs":[{"name","bytes","sha256","slice":null|[0,rows]}],
 "skipped_buffers":[{"name","rule"}],
 "measurements":{"save_seconds","save_bytes"}}
```

Cross-checks at every full load (restore, full inspect): `fields.tsv` == rendering of the parsed
manifest (its `manifest_sha256` row is the manifest's seal); `tokens.bin` length/sha;
`token_history` == the last two tokens of H (the engine's host mirror rule); the device control
blobs agree (`position` == N, `next_token` == t, `token` == H[N-1], `token_history` blob == the
pair, `error` == 0); every blob's bytes and sha256; `save_bytes` == sum of blob bytes.

### Tokenizer/template identity

[`one-card/tokenizer-identity.tsv`](one-card/tokenizer-identity.tsv) holds pins the harness
already had: the GGUF header sha256 of shard 1 (`7c1460a9…`, which contains the tokenizer
vocabulary/merges and `tokenizer.chat_template`; pinned by the lane's admission receipt and every
suite `input.json`), the tokenizer source `packet2-cpu-oracle/tokenizer.py` (`1c284c06…`) and the
decoded vocabulary table (`7a0e6124…`). Format: `KEY<TAB>VALUE` lines, `#` comments; required
`format=ownrt.tokenizer-identity.v1` and the three 64-hex pins. Save records the file's sha256
and the three pins; restore refuses (`tokenizer identity`) unless the supplied file is
byte-identical. The engine does not tokenize; the caller attests the identity it used.

### result.json `checkpoint` object (every request; additive)

```
"checkpoint":{"contract":"v1.2+p180","label":"experimental","operations":[…],   // e.g. ["append","save"]
  "restore":null|{"checkpoint_id","manifest_sha256","operation":"same-generation-resume"|"append",
    "saved_prefix_length":N,"saved_history_length":N+1,"saved_prompt_length","input_length",
    "appended_length":len(D) (0 for resume),"pending_token":t,"pending_is_stop":bool,"pending_token_handling":text,
    "restore_ms","append_prefill_ms":ms|null,"restored_bytes"},
  "save":null|{"checkpoint_id","manifest_sha256","position","pending_token","bytes","seconds","parent_checkpoint_id":id|null}}
```

`checkpoint_restore_ms` (packet179) is kept. `prefill_ms` is the append prefill for an append,
0 for a same-generation resume; `first_generated_token_ms` is now recorded for a resume too (its
first step), and the owner receipt's decode time is taken before the checkpoint save I/O. Each restore also prints
`{"event":"checkpoint-upload-begin",…}` on stderr immediately before the first upload, so a
refusal can be proven to precede it.

### Inspect output (stdout: exactly one JSON object; stderr: JSON lines)

```
{"schema":"ownrt.checkpoint-inspect.v1","ok":true|false,"mode":"full"|"metadata","device_required":false,
 "checkpoint_dir","checkpoint_id",
 "label","contract","manifest_sha256",                                  // only when ok
 "verified":{"manifest_seal":true,"fields_tsv_cross_check":true,"file_set_closed":true,
             "tokens":true|null,"semantic_blob_checks":true|null,
             "blobs_verified":n|null,"blob_bytes_verified":bytes|null}, // null in metadata mode
 "manifest":{…the manifest object verbatim…}|null,
 "error":null|{"check","detail"}}
```

stderr lines: `{"event":"inspect-start",…}`, one `{"event":"blob-verified","name","bytes"}` per
blob (full mode only), `{"event":"inspect-end","ok"}`. Exit 0 iff `ok`. Metadata mode reads no
blob and not `tokens.bin` (CPU-proven with every blob unreadable). Both modes take the shared
lock and refuse (`lock`) while a save/delete holds it.

### Delete output

```
{"schema":"ownrt.checkpoint-delete.v1","ok","deleted","checkpoint_dir","checkpoint_id","files_removed",
 "reason":null|"in_use"|"not_a_checkpoint"|"io","error":null|{"check","detail"}}
```

Delete first validates the target **without creating a lock** (manifest parses, label
`experimental`, `checkpoint_id` names the directory, `fields.tsv` cross-check, closed file set),
then takes the exclusive lock non-blocking (`in_use` if any restore/inspect/save holds it),
re-validates, removes `manifest.json` first (the checkpoint is invisible from then on), then the
rest of the manifest's file set and the directory, and unlinks the lock file while still holding
it. Only a busy lock reports `in_use`; other lock failures report `io`. Other lock holders re-check the lock inode after acquiring.

## CPU gates (all passed; receipts in `one-card/evidence/` and `evidence/`)

| Gate | Receipt | Result |
| --- | --- | --- |
| Native delta + harness edits | `native-delta.json`, `delta-check.json` | entry TU only; every other copied file byte-equal to packet179 after path relocation |
| Device build | `build.json`, `identity-check.json` | icpx compile 25 s + link 3 s; 41 kernel objects sha-asserted vs packet165 |
| Host-only C++ sessions | `checkpoint-probe.json` | 59 native runs: packet179 round trip; append == fresh reference; restore-then-save chain ×2 == reference; repeat append and a fresh one-shot save hold **byte-identical state blobs**; empty-delta append == resume; inspect modes; 26 refusal/boundary cases, every refusal before the upload marker and labelled before/after model load; 10 delete cases; real concurrent delete-vs-restore (`in_use`, restore still exact); packet179's real 128-blob device checkpoint passes this C++ reader (metadata + full + real control-blob checks) and its TSV tamper is refused |
| Lifecycle worker arm (production shape) | `lifecycle-test.json` | real `worker.lifecycle()` with mocked native: 87-token P, K=256, 126-token T, NEW=469, 128-blob manifests; 12 cases incl. append/chain/repeat/state/save mismatches failing with the first index and both streams, natural stop at 100 (not evaluable → fail) and at 150 (passes), EOS in save, native failure |
| packet179 real receipts | `p179-receipt-replay.json` | packet179 `checkpoint_check` reproduces its own receipt; streams/drain; manifest semantics on the real gate; row-a identity gate on real outputs (cross-checked against summary.json); aggregate + full512 report reproduce 31.85 tok/s |
| Inherited | `analyzer-tests.json`, `report512-test.json`, `real-arm-sequence.json`, `native-sequence.json`, `device-path-imports.json`, `preparation-probe.json`, `flags.json`, `../evidence/packet163-replay.json` | unchanged gates re-run on this packet |

Refusals proven on CPU (check name in brackets): corrupt blob [blob sha256], wrong prompt
[prefix], binary mismatch [engine identity], geometry [geometry], manifest edit [manifest
sha256], TSV-only `history0` edit [manifest cross-check], consistent JSON `token_history` edit
[token state], append prefix mismatch at index 3 [prefix], wrong pending token [prefix], length
neither rule [prefix], tokenizer file differs [tokenizer identity], tokenizer file missing
[argument], extra file in the directory [file set], save target exists [never overwrite],
save id == restore id [argument], exclusive lock held [lock], resume after a stop token [ended
generation] (append after it allowed), resume beyond the context, with and without a save
[context] (resume exactly to the last position allowed), save with a malformed tokenizer file
[tokenizer identity, nothing written], plus `--checkpoint-save-id` without restore,
`--tokenizer-identity` without a checkpoint mode, ids `..` and `x.lock`. Corrupt blob, binary
mismatch and geometry are refused after the model load (engine-dependent or full-read checks);
every other refusal happens before it.

## Device rows (proposal only: `ops/lane-queue/proposed-p180-one-card-A.txt`)

Admission exactly as packet179's rows: lane A whole-host reservation, fault review
(`one-card/fault_review.py`), host memory admission 98,990,252,032 bytes available, device storage
floor 25 GB (`screen.py`, at start and throughout), lane-queue storage floor 25 GB +
`planned_write_bytes` at plan/launch, worker supervision 7200 s (`screen.py`), native
`--seconds 7200` and `--wait-seconds 600` per process. `planned_write_bytes` is 400 MB (row b
writes S1 ≈ 69 MB, S2 and S2b ≈ 76 MB each, five native folders; S2b blobs are deleted by the
delete-tool gate). Root had 36 GB free when sealed.

| Row | What | Estimate |
| --- | --- | --- |
| `packet180-one-card-full512-A-a` | full512 suite as packet179 row a (one load, 13 requests, oracle-128). **Every request's full output must equal packet179 row a** (`run/p179-identity.json`, compared with `reference-p179-row-a.json`, a copy of packet179's receipts) | ~8–9 min (packet179: 499 s); plan range 450–900 s |
| `packet180-one-card-lifecycle-A-b` | five fresh processes: (1) `save-s1`: P=incident-retrospective, K=256, save S1 (N=342); (2) `append-s2`: restore S1 + NEW = P + gen[0:256] + T (469 tokens) + decode M1=128 + save S2; (3) `resume-s2`: restore S2 (same-generation, `--input NEW`) + decode M2=64; (4) `reference`: fresh run of NEW decoding 192; (5) `append-s2b`: repeat of (2) into S2b; then inspect-metadata S1/S2/S2b, full inspect S2/S2b, delete S2b | ~21 min (5 loads × ~210 s + requests; packet179 legs 218–251 s each); plan range 1100–2400 s |

T is the first 126 tokens of the suite's `prefill512` document excerpt (no 248044/248046),
recorded in [`one-card/lifecycle.json`](one-card/lifecycle.json) and re-derived from its source
file at run time. Row b gates: (2) == reference[0:128]; (3) == reference[128:192]; (5) == (2);
S2b blobs == S2 blobs; save tokens == packet179 row a [0:256] and oracle-128; every
result.json checkpoint record; manifests (identity, lineage, semantics); host tools. If the
reference stops naturally within 128 tokens the chain gate is reported as not evaluable and the
row fails (the resume leg would also be refused: S2's pending token would be a stop token). **A divergence is a FAILURE**: `run/lifecycle-receipt.json` keeps the first divergent
index and both full streams. Reported, not gated: restore ms, append-prefill ms, save seconds and
bytes per checkpoint, and cold prefill of NEW (reference) vs restore + append prefill.

Numbers above and where they apply: 27 GB = CPU build/probe stop (`build_engine.limits`, this
host's CPU scripts only); 25 GB = device floor (screen, during the row) and lane-queue floor;
7200 s = screen watchdog on the worker child; 600 s = native per-operation wait and the
worker's bound on each device-free host tool; 60 s = CPU-probe-only wait for the concurrency
hook; estimates and `expected_seconds` are informational (no runner enforces them).

## Packaging order and checks

`scaffold.py` (once) → `adapt_native.py` → `build_checkpoint.py one-card` → `checkpoint_probe.py`
→ `test_measurement.py`, `test_report512.py`, `test_sequence.py`, `test_lifecycle.py`,
`test_p179_receipts.py` (each `one-card`), `test_packet163_evidence.py`, `probe_imports.py`,
`capture_flags.py one-card`, `native_sequence_probe.py one-card`, `verify_delta.py` →
`package_rows.py` (seal + proposal) → `validate_flags.py` → `check_queue_rows.py` (live planner
and rehearsal on a private copy) → `final_checks.py` → `final_checks.py --ready` (writes READY
last, re-runs `pin_guard.check_job` on both rows over the full closure and classifies every
pin). All CPU commands: `nice -n 19 taskset -c 8-15,24-31 … </dev/null` from the repo root.
Result at sealing: seal 547 files; live planner `passed` for both rows before and after READY;
pin guard on the full closure after READY: 613 pins = 605 in-packet + 7 packet49 oracle-binding
targets + 1 own proposal, 0 cross-packet mutable. Commit note: the seven sealed
`one-card/lineage/packet179-receipts/row-b/run/checkpoints/gate/*.bin` copies match the
repository's `*.bin` ignore rule and need `git add -f` (as packet179's blobs did).
Every pin is packet-private: packet179 receipts are byte copies under
`one-card/lineage/packet179-receipts/` (COPY-MANIFEST.json), the host probe links in-packet
copies of the packet58aj objects, and the native-sequence probe compiles in-packet copies.

## Not claimed

- No device result: nothing here qualifies arithmetic, append exactness on the real model, or
  performance. The CPU state equivalence is in the mini geometry only.
- The label stays `experimental`; changing it is the revision after this one passes.
- Not portable model identity (host-local stat pins, as packet179); no TP2/MTP checkpoints; no
  selective prefix truncation; no compression; ctxkeeper does not call these operations yet.
- The tokenizer identity is attested by the caller's file; the engine never tokenizes.
- A stray `ROOT/ID.lock` without `ROOT/ID/` (possible only in a restore racing a delete) is
  inert. The failed-save cleanup path is reviewed but not failure-injected on CPU.
- An independent read-only review of the native delta found nothing must-fix; its six
  should-fix items (resume context bound, early tokenizer check, stop-token resume, resume
  first-token time, decode time excluding the save, failed-save cleanup) and the useful nits
  (fd on write failure, delete order, `in_use` only for a busy lock, `.lock` ids, skipped-buffer
  count, blob byte bound, control blobs required) are applied and re-gated.
