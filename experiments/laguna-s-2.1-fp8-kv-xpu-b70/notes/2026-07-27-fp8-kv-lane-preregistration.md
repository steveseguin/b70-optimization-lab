# Laguna calibrated-FP8-KV lane preregistration

Date: 2026-07-27 America/Toronto

Status: active bring-up; no throughput claim yet.

## Why this is a new lane

Poolside's quantized Laguna checkpoint specifies static, symmetric, per-tensor
FP8 KV with 96 calibrated scalar K/V scales. The sealed 2026-07-26 record
overrode that default with BF16 KV to satisfy its BF16 q1 bitwise contract. It
is not being rewritten.

The new lane uses explicit `--kv-cache-dtype fp8`, retains BF16 activations,
and disables runtime scale calculation. Target FP8 output will naturally
differ from BF16 output, so the exact oracle is a newly generated target-only
FP8 q1 run. Archived BF16 output remains a semantic comparison, not a bitwise
gate.

## Frozen starting identity

- target revision: `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft revision: `5e07c246915c86dc6920fead03d019989224f2ba`;
- vLLM base: `e596ef1543466ae1a05e5bb8091f58872e2b18ba`;
- FP8-lane vLLM head: `c2dd002ff11a156392b8ba429ffd7259deae810c`;
- XPU kernels: `6f9dd3c3a7b1b677a992ca4f431a968408f9c816`;
- TP4 + EP4, one active sequence, max length 8192, block size 64;
- candidate: exact width 12, DFlash depth 11, 146/145 Breakable topology;
- target scale digest:
  `3e6df440976ab2ed5229e1a39179cbc99d573c615386f223eeabc9de5ea9ddc0`.

The target must report 48 calibrated FP8 cache layers on all ranks. The DFlash
checkpoint has no KV quantization config; its six attention layers inherit the
global FP8 cache dtype with unit scales. That is explicitly labeled
`unit_uncalibrated` and must not be reported as checkpoint-calibrated.

## First experiment sequence

1. target-only eager FP8 q1, 13 cold prompts, 512 output tokens;
2. width-12/depth-11 FP8 DFlash candidate against that teacher;
3. a second fresh-start confirmation of any valid candidate;
4. profile cache insertion and paged attention before changing kernels;
5. only then test one isolated optimization at a time.

Required gates are cache-zero, 13/13 token and text equality within FP8, target
and draft scale audits on all ranks, Flash Attention without fallback,
146/145 candidate topology, clean teardown, and separate semantic/long-context
quality tests.

## Prior evidence and expectations

An older matched width-8/depth-7 short-context A/B measured FP8 at
`46.956936 tok/s` versus BF16 at `48.980858 tok/s` (`-4.132%`) while exactly
doubling cache capacity (`110,995` to `221,990` tokens). Acceptance did not
degrade. The evidence localizes the loss only to the per-cycle cache/attention
path; it does not prove whether quantization, cache write, or paged read is the
cause.

Therefore:

- FP8 capacity is expected and will be verified, not treated as a speed win;
- short-context throughput may initially regress;
- no optimization is accepted by projection;
- `--calculate-kv-scales`, E5M2, persistent BF16 KV views, BF16 hash equality,
  width 14/16, draft graph capture, and local argmax are not first-lane work.
