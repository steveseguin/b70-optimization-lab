# Flash-Next TP4 eager MTP0 fixed-vision attempt 2 preregistration

Date: 2026-08-28

## Purpose and credit boundary

Attempt 2 is the first launch-eligible bounded vision-enabled screen for only
the current-runtime TP4/EP4, eager, MTP0, active-context-0, automatic-KV,
fixed-vision-fixture-v1 cell. Attempt 1 is administratively closed without a
model run. Attempt 2 can earn at most Grade-C `lab-screened` capability and
bounded quality evidence after every admission, server, client, health, and
teardown gate passes. It grants no decode, prefill, TTFT, deployment, graph,
other-topology, other-MTP, other-context, or other-modality credit and cannot
replace or lower any prior text result or speed.

Packet construction does not launch the supervisor, model, or client.

## Frozen model and test identity

- checkpoint `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, XPU kernels
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, staged runtime
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, all-gather/reduce-scatter, Triton MoE, eager, MTP0, no reasoning
  parser, 512 maximum model length, 64 maximum batched tokens, one sequence;
- unchanged accepted selective UVA placement: PLE n-gram plus input embedding
  under the 12.25-GiB per-rank budget;
- fixed 201,326,592-byte BLHNC KV cache, automatic KV dtype, 64-token blocks,
  prefix caching disabled;
- multimodal loading enabled, exact image-one/video-zero prompt limits,
  processor cache 0 GiB, encoder TP mode `weights`;
- same-boot exact text recovery, the same seven deterministic semantic cases,
  then the same three committed grounded vision cases repeated three times
  (nine requests), followed by health and clean descendant-aware teardown;
- port `19677`; every state, run, evidence, cache, compile, and RPC path is
  fresh and contains `attempt2` or `vision-a2`.

## Frozen packet hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `f3aff8be5518a9d4694df8ff4e5486a42a0a366323f5917781b2b2053bf8b716` |
| `tools/launch-tp4-mtp0-current-vision-a2.sh` | `f85720f0e12111febdbb290f97d50a1f3c1d24a0571b40f8712fee46a6f8b8c2` |
| `tools/run-tp4-mtp0-current-vision-a2-client.sh` | `7a41ca301cb3ee315cd83e0a25fe7befb3ba2838c17f3a5520bc89424f7e46dd` |
| `tools/supervise-tp4-mtp0-current-vision-a2.sh` | `0c64ccb22b2afeecbe279d96064187ab2f517d2933911eb58e4778db76bb970e` |
| `tools/run-fixed-vision-fixture-v1.py` | `f84e7f02d98c611095b2bae9582fc1056c3e042969733d1ef4290910cd40e0a1` |
| `fixtures/fixed-vision-fixture-v1.json` | `395158995f300e53d4360b844bcbb8dffb2dd551eb0106f4d91200b9c7402226` |
| `fixtures/fixed_vision_fixture_v1.py` | `82bc70952db0b00368d7142569f239763d07075aed270b8b7fa14b1062066345` |
| `scripts/qwen38-text-quality-suite.py` | `8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de` |
| `scripts/check-qwen36-xpu-xccl-health.sh` | `b15dd4c248d8c4d7035c2d180b9ecc5354b1b20bdabb0c47c540b5003a1cfb78` |
| `tools/xccl_probe.py` | `6ecd340651a6780fdbe0bd57d346540efe168bf2e3175d54e10dd8660ed5b30a` |

## Strong recovery admission

Before model launch, the supervisor verifies the committed graph-attempt-5
result and evidence-manifest hashes and requires its clean teardown fields. It
then requires both system and user managers to report `running`, no failed
system units, and `user@1000.service` continuously active for at least 900
seconds. The preceding 15 minutes of kernel records must contain no host-memory
exhaustion, storage-receiver, or addressed B70 failure marker.

Admission also requires at least 110 GiB available RAM, 6 GiB free swap, 80
GiB root space, 300 GiB external evidence space, and 32 GiB shared-memory
space; no archival, model, worker, or collective process; the fresh port; four
exact rediscovered B70s below 256 MiB each; four successful single-card checks;
and one four-rank all-reduce receipt. All recovery inputs and outputs are
hashed into `admission-recovery.sha256` before the model starts. The launcher's
own frozen collective still runs separately.

The 15,000-second supervisor and 10,500-second client-remaining-life gates are
unchanged. During the model lifecycle, the strengthened stop floors are 10 GiB
available RAM and 5 GiB free swap. Any admission, identity, server, text,
vision, health, resource, or teardown failure stops without retry and preserves
partial artifacts. No family or measurement row may change until a separate
closeout reviews immutable run and supervisor evidence.
