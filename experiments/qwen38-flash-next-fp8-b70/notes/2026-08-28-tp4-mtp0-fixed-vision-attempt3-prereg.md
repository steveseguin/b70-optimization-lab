# Flash-Next TP4 eager MTP0 fixed-vision attempt 3 preregistration

Date: 2026-08-28

## Purpose and sole treatment

Attempt 3 is a fresh retry of the bounded current-runtime TP4/EP4 eager MTP0
fixed-vision screen. Attempts 1 and 2 are administrative closures without a
model launch. The sole treatment from attempt 2 is replacement of the broad
command-text process gate with an ancestor-aware, exact runtime-owner
classifier. No model, performance, placement, cache, quality, timeout, or
interpretation field changes.

The arm can earn at most Grade-C `lab-screened` capability and bounded quality
evidence after every admission, server, client, health, and teardown gate
passes. It grants no decode, prefill, TTFT, deployment, graph, other-topology,
other-MTP, other-context, or other-modality credit and cannot replace or lower
any prior text result or speed. Packet construction does not launch anything.

## Frozen identity

- checkpoint revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernels
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, staged runtime
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, all-gather/reduce-scatter, Triton MoE, eager, MTP0, 512 maximum
  model length, 64 maximum batched tokens, one sequence, no reasoning parser;
- unchanged PLE n-gram plus input-embedding selective UVA placement;
- fixed 201,326,592-byte BLHNC automatic-dtype KV cache, 64-token blocks,
  prefix caching disabled;
- multimodal loading enabled, image-one/video-zero prompt limits, processor
  cache 0 GiB, encoder TP mode `weights`;
- exact same-boot text recovery, seven semantics, nine committed fixed-vision
  requests, final health, and clean descendant-aware teardown;
- port `19681`, state prefix `/tmp/q38-mtp0-current-vision-a3`, and wholly
  fresh attempt-3 run, evidence, cache, compile, and RPC paths.

## Frozen packet hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `f3aff8be5518a9d4694df8ff4e5486a42a0a366323f5917781b2b2053bf8b716` |
| `tools/launch-tp4-mtp0-current-vision-a3.sh` | `b2d0080dbee1ff5d1c49444ed009d5f9fcac4bf2d7aaa840b3d3190ae380b874` |
| `tools/run-tp4-mtp0-current-vision-a3-client.sh` | `166d109587e9733c045e34d8153cbbebdd9ee9fd7758f785b4c064c7fca119dd` |
| `tools/supervise-tp4-mtp0-current-vision-a3.sh` | `13d3528defe1c94ff3829c84ab8969d994f5bb9e995f608b3221cd9698c0e747` |
| `tools/classify-q38-runtime-conflicts.py` | `c6f9ee76fec1f3343c223ac8264312b6ec3ae6ad6c242e8154fb5d3e3d0ae390` |
| `tools/test-q38-runtime-conflict-classifier.sh` | `fe146ba53bf0eb2f0c0ea60647fbdace353a39a564317e6375574815c2c2dd85` |
| `tools/run-fixed-vision-fixture-v1.py` | `f84e7f02d98c611095b2bae9582fc1056c3e042969733d1ef4290910cd40e0a1` |
| `fixtures/fixed-vision-fixture-v1.json` | `395158995f300e53d4360b844bcbb8dffb2dd551eb0106f4d91200b9c7402226` |
| `scripts/qwen38-text-quality-suite.py` | `8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de` |
| `scripts/check-qwen36-xpu-xccl-health.sh` | `b15dd4c248d8c4d7035c2d180b9ecc5354b1b20bdabb0c47c540b5003a1cfb78` |
| `tools/xccl_probe.py` | `6ecd340651a6780fdbe0bd57d346540efe168bf2e3175d54e10dd8660ed5b30a` |

## Admission and stop rules

The classifier fixture runs before live classification. It proves clear
receipts for the supervisor pathname, legacy broad-search command, and a safe
empty-cmdline process. It requires exact conflicts for vLLM serve/API argv,
torch distributed, XCCL, and empty-cmdline Worker/APIServer/EngineCore comm
names including Linux truncation forms. It also requires failure for a
runtime-positive structurally excluded PID, missing and unreadable required
process fields, PID/starttime reuse, mixed conflict-plus-read-error evidence,
and a fabricated supervisor starttime, then verifies the binding against live
`/proc` ancestry.

Production scans bind the exclusion structurally to this exact live supervisor
PID, starttime, canonical script token, scanner child, and current direct
parent. Runtime-positive classification overrides exclusion. Every readable
process gets a PID/PPID/starttime receipt; any read failure, stat/status
mismatch, or identity change exits 2 and fails closed. Conflicts exit 1 and a
fully readable clear scan exits 0.

The supervisor performs one clear scan before card work and a second clear
scan immediately after the XPU/XCCL health gate, before any model launch. Both
JSON/RC/stderr receipts and both full process tables enter the admission hash.
Postflight runs the same classifier after owned teardown; its explicit return
code and structurally bound JSON are mandatory clean-teardown gates rather
than report-only evidence.

All other attempt-2 recovery gates remain: pinned graph-attempt-5 clean
closeout; clean system and user managers; user manager active for at least 900
seconds; 15-minute clean kernel window; 110 GiB available RAM, 6 GiB free swap,
80 GiB root, 300 GiB external, and 32 GiB shared-memory floors; no archival
overlap; four exact idle cards; four single-card checks; and a four-rank
collective. The lifecycle remains bounded at 15,000 seconds, the client needs
10,500 seconds remaining, and live floors remain 10 GiB available RAM and 5
GiB free swap.

Stop without retry on any identity, admission, fixture, runtime-owner,
resource, server, text, vision, health, or teardown failure. Preserve partial
artifacts. Do not add a family or measurement row until a separate closeout
reviews immutable evidence.
