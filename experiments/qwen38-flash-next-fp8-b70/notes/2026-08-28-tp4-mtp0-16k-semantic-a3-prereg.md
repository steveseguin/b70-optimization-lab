# Qwen3.8 Flash-Next FP8 TP4 MTP0 active-16K semantic A3 preregistration

Date: 2026-08-28
Status: frozen before execution

## Purpose and protected boundary

Upgrade the existing TP4/EP4/eager/MTP0 active-16K Grade-D structural screen
with a natural retrieval oracle, one same-server deterministic repeat, and one
fresh-server repeat. The prior exact-depth result and its diagnostic
`5.219484116949911 tok/s` observation remain intact. These semantic requests
do not replace or lower that result and receive no speed credit.

The post-reboot Stage A3/B1 recovery chain passed and authorizes this one
separately registered matrix arm. B1 retained corrected receiver events for
local NVMe `0000:01:00.0`, so both A3 boots read the verified byte-identical
external checkpoint at
`/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`. Model load time is not a
benchmark metric. Any local-NVMe event, I/O error, B70 reset/fatal event,
failed semantic field, cache reuse, output divergence, lifecycle failure, or
timeout stops the arm.

## Frozen identity

- model revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, 144 files,
  131 shards, and 185,563,783,127 bytes;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernel source
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, staged runtime
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, Triton MoE, eager/graph-off, MTP0, max length 16,512, 33-block
  358,465,536-byte fixed cache, one sequence, 64 batched tokens, prefix cache
  disabled, and accepted 12.25-GiB/rank selective UVA placement;
- semantic harness `scripts/bench-openai-long-context-suite.py`, SHA-256
  `f3bbf3369152a55aa0c9acc8bbad7ff15db2d4d694f03cb5ed275efde7f99459`;
- calibrated suite `fixtures/long-context-semantic-16k-v1.json`, SHA-256
  `61d94377bcb5a8252d4796d27ab0a16714c4c603bb20e8f5533641cb9e982e6a`;
- launcher `tools/launch-tp4-ep4-eager-mtp0-16512-semantic-a3.sh`, SHA-256
  `77bb994470ebc67e4c27bdb07ff5e002ecc5fc3c213e0ada7aa0ef23b42c4306`;
- supervisor `tools/supervise-tp4-mtp0-16512-semantic-a3.sh`, SHA-256
  `261cc8d39cf4dc7d1460e1d73907e2a3f86f375d8afd6d014cbf7b983549df88`;
- client `tools/run-tp4-mtp0-16512-semantic-a3.sh`, SHA-256
  `1526e76c98c604d788e72f0de76e20617c81242e03c4d9e77332dd2d2509e025`.

## Two-boot program

Phase 1 uses attempt 3, port 19675, and fresh state/cache/compile/RPC/evidence
paths. It sends the same deterministic non-thinking retrieval task twice on
one server. Each request must contain 16,000--16,400 actual prompt tokens, fit
within 16,512 including output, return the exact five JSON fields, expose a
complete token-id stream, and report zero cached tokens. Prompt, text, and
token-id hashes must match across both responses.

Only a complete Phase-1 pass authorizes Phase 2. Phase 2 uses attempt 4, port
19676, distinct fresh paths, and a distinct server PID. It sends the same task
once and must reproduce the Phase-1 prompt, text, and token-id hashes with the
same semantic and cache-zero gates. Each phase owns controlled shutdown and a
postflight requiring four exact idle cards, no process/listener/temp-path
residue, and a clean B70 plus local-NVMe journal window.

Three semantic passes, same-server equality, fresh-server equality, and both
clean postflights classify the TP4/MTP0/16K text cell as
`grade-c-research-screened`. This is context-quality credit only: the known
short 6/7 semantic boundary remains, and no deployment, headline, or new speed
claim is authorized.
