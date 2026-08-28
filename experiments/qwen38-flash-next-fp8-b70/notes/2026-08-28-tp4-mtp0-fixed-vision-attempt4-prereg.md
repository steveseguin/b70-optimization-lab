# Flash-Next TP4 eager MTP0 fixed-vision attempt 4 preregistration

Date: 2026-08-28

## Purpose and sole treatment

Attempt 4 is a fresh retry of the bounded current-runtime TP4/EP4 eager MTP0
fixed-vision screen. Attempt 3 reached only API-process construction and failed
before EngineCore workers or model loading because its generated ZMQ IPC path
was 109 bytes against a 107-byte limit. The sole runtime treatment is shorter
temporary roots: `/tmp/q38v-a4-c` for compilation and `/tmp/q38v-a4-r` for RPC.

The base adds administrative fail-closed receipts for the derived IPC address
and classifies an exact IPC-limit failure before consulting downstream worker
offload receipts. These guards do not change model execution. Every model,
runtime, placement, cache, modality, quality, timeout, classifier, and
performance field remains identical to attempt 3.

The arm can earn at most Grade-C `lab-screened` capability and bounded quality
evidence after every admission, server, client, health, and teardown gate
passes. It grants no decode, prefill, TTFT, deployment, graph, other-topology,
other-MTP, other-context, or other-modality credit and cannot replace or lower
any prior speed. Packet construction does not launch anything.

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
- port `19682`, state prefix `/tmp/q38-mtp0-current-vision-a4`, short compile
  and RPC roots above, and fresh attempt-4 run, evidence, and cache paths.

## IPC fixture and failure order

The frozen UUID fixture is `ffffffff-ffff-4fff-bfff-ffffffffffff` (36
characters). Combined with `/tmp/q38v-a4-r`, the derived filesystem address is
51 bytes, 56 below the 107-byte runtime limit. The prior root derives to 109
bytes and is rejected by the same fixture. The supervisor runs and records the
fixture before card work; the base independently writes
`ipc-path-preflight.json` before any server start and asserts the live pyzmq
limit is exactly 107.

On unhealthy startup, an exact ZMQ over-limit signature is now classified
first. A server log with no `Worker_TP` record is classified next as a
pre-worker stop. Only a log that reached workers can be interpreted through
per-worker offload receipts. The policy fixture verifies that order.

## Frozen packet hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `487f088481c0c7f5e821bdce7dda41bb20aa0761c4453215a0662f23473beb46` |
| `tools/launch-tp4-mtp0-current-vision-a4.sh` | `72e269517e1a58a6473686b7824a8654da25a7a52b3db5dc830394ee47b6f9d8` |
| `tools/run-tp4-mtp0-current-vision-a4-client.sh` | `590f6b6cd09af03ba5d2361ebf3d0129494b3d231ab4e9129008561068217a78` |
| `tools/supervise-tp4-mtp0-current-vision-a4.sh` | `74aba0981af68db967d96fc5facc7b41672ec3bb6f9473022bd3fb07afba8ba2` |
| `tools/classify-q38-runtime-conflicts.py` | `c6f9ee76fec1f3343c223ac8264312b6ec3ae6ad6c242e8154fb5d3e3d0ae390` |
| `tools/test-q38-runtime-conflict-classifier.sh` | `fe146ba53bf0eb2f0c0ea60647fbdace353a39a564317e6375574815c2c2dd85` |
| `tools/test-q38-vision-ipc-path-policy.sh` | `a1f513431107cdee860b649c96bcd8295f2840b504bcde8fee260834008b2477` |
| `tools/run-fixed-vision-fixture-v1.py` | `f84e7f02d98c611095b2bae9582fc1056c3e042969733d1ef4290910cd40e0a1` |
| `fixtures/fixed-vision-fixture-v1.json` | `395158995f300e53d4360b844bcbb8dffb2dd551eb0106f4d91200b9c7402226` |
| `scripts/qwen38-text-quality-suite.py` | `8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de` |
| `data/20260828-tp4-mtp0-fixed-vision-attempt3-result.json` | `089e51130d68cc67c1c4a4a0009cc1f43501c17b0ba90a7ea2cd7049e0570e23` |

## Admission and stop rules

All attempt-3 recovery gates remain, including pinned graph-attempt-5 and
attempt-3 closeouts, clean system/user managers, the 900-second and 15-minute
recovery windows, resource floors, exact idle cards, XPU/XCCL health, and the
structurally bound runtime-conflict scans before card work, immediately before
model launch, and after teardown. The lifecycle remains bounded at 15,000
seconds, the client needs 10,500 seconds remaining, and live floors remain 10
GiB available RAM and 5 GiB free swap.

Stop without retry on any hash, identity, path, IPC fixture, admission,
runtime-owner, resource, server, text, vision, health, or teardown failure.
Preserve partial artifacts. Do not add a family or measurement row until a
separate closeout reviews immutable evidence.
