# Qwen3.8 Flash-Next TP4 MTP3 official-quality preregistration

Date: 2026-08-27

## Purpose and preservation boundary

The target-only official-thinking profile passed 25/25 preregistered responses.
The preferred exact-4K MTP3 speed recipe separately passed deterministic target
parity and measured `15.501565106 tok/s` decode. This bounded arm tests whether
the official quality profile transfers to MTP3. It collects no timing rows and
cannot replace, lower, or relabel any existing MTP0 or MTP3 speed result.

The active weights and MTP remain in VRAM. The 51B PLE/input state remains
pinned in host RAM and GPU-addressable through UVA. Maximum model length stays
4,352, the practical 4,096-input plus 256-output deployment envelope.

## Storage gate

This is the first planned run from the local NVMe checkpoint path:

```text
/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
```

Do not launch until the copy from the preserved external checkpoint has
completed and a content verification reports no difference. The local
`config.json`, weight index, all 131 safetensor shards, and complete artifact
tree must match the retained revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`. A storage-copy failure is not a
model/runtime result.

## Frozen server identity

- campaign: `qwen38-flash-next-fp8-tp4-ep4-eager-mtp3-4352-r1`
- attempt: `2`
- port: `19647`
- TP4/EP4, eager/graph-off, text-only;
- MTP3;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- staged XPU runtime built from kernel source
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- maximum model length 4,352, one sequence, batched-token cap 64;
- fixed BLHNC automatic-KV cache `294195200` bytes, exactly 25
  current-source blocks;
- prefix caching and async scheduling off;
- reasoning parser `qwen3`;
- no diagnostics.

New immutable roots:

```text
/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp3-4352-r1-attempt2
/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp3-4352-r1-attempt2
```

Frozen SHA-256 values:

- base launcher:
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- MTP3 official-quality wrapper:
  `48184ea61eaef677cda891eefc06899f1a20f0499e91019ec323889bdf3242e3`;
- deterministic quality helper:
  `8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de`;
- official-quality helper:
  `c3a63b8a456379e7c345a9efb8a55e6ae1db0dca94c0be3b7ba88478ce7eed95`.

Target baselines:

- sealed deterministic exact-4K MTP0 JSON:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt1/quality-v2-short-and-4k.json`;
- target official-thinking JSON:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt2/official-thinking-quality.json`,
  SHA-256
  `ad6516145dbbf9b41f9a2c5a761d5245ac0f6cf11d63e2a1130f4e6c4b03f04e`.

## Frozen gates and order

1. Require the verified local checkpoint, absent run/cache roots, idle port,
   all four discoverable B70s, exact source/runtime identities, and exactly one
   MTP3 speculative configuration.
2. Require a healthy API, four 12.22-GiB host-placement receipts, 32.06-GiB
   model-load accounting per rank, exactly 25 cache blocks, and capacity at
   least 4,352 tokens. Stop on a fit or identity failure.
3. Replay the deterministic non-thinking quality-v2 suite against the sealed
   MTP0 baseline with 16 repeats and the exact 4K needle. Require 26/26 baseline
   comparisons, 16/16 one-hash repeats, exactly 4,096 server prompt tokens,
   complete usage, and zero cache reuse. The known code miss may keep the
   helper aggregate false; no other failure is allowed.
4. Run the unchanged official-thinking helper. Require scout 4/4 and grid
   21/21, nonempty separated reasoning/final fields, normal stops, complete
   usage, and zero cached/created-cache tokens for all 25 responses. Stop on
   the first semantic or structural failure. Treat an output-limit stop as
   inconclusive.
5. Compare case order, seeds, sampling identity, normalized final answers, and
   full reasoning/final hashes with the target-only official JSON. Report exact
   agreement counts. Because this is a sampled profile, exact text divergence
   alone is not called corruption if every semantic and structural gate passes;
   it does, however, prevent an exact-thinking-parity claim.
6. Capture cumulative speculative counters only after quality. They are
   session-level descriptive evidence, not per-case acceptance or speed.
7. Stop normally and preserve process, journal, and storage-health evidence.

No throughput request, warmup-for-timing sequence, or LocalMaxxing submission
is authorized. A pass qualifies MTP3 for this official target-quality battery;
it does not seal fresh-boot determinism, production multi-user serving, graph,
vision, or longer context.
