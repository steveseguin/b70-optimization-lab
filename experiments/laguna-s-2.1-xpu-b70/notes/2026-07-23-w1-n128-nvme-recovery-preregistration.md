# Laguna routed-W1 N128 local-NVMe recovery endpoint preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: this is a distinct recovery campaign. No local-NVMe
endpoint service, model generation, candidate measurement, or performance
observation has occurred under this campaign.

## Lineage and storage boundary

This protocol inherits the complete treatment, benchmark, quality, honesty,
phase-one, full-ABBA, and promotion rules from
[`2026-07-23-routed-w1-n128-endpoint-preregistration.md`](2026-07-23-routed-w1-n128-endpoint-preregistration.md).
That original registration is retained as the authoritative detailed statement
of every unchanged threshold and exact/cold/cache-zero rule.

The original failed campaign root
`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-endpoint-abba-8936aac-c59aaad-20260723T093923Z`
and the post-reboot NTFS3 preflight-abort root
`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-postreboot-recovery-20260723T120411Z`
are immutable historical evidence. They are not campaign legs, are not copied
into this result, and cannot be reused or retried.

The external Corsair USB volume is backup-only. No live model read, manifest
read, cache, temporary file, service log, campaign root, or evidence write may
use `/media/steve/CorsairExternal`. Active paths are fixed to:

```text
models:    /mnt/fast-ai/llm-models/laguna-s-2.1/{int4,dflash-int4}
artifacts: /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1
campaign:  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-recovery-abba-8936aac-c59aaad-20260723T131632Z
```

The aggregate relative-path model manifest at
`/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/nvme-files.sha256` is
pinned to
`45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac`.
The independently generated source manifest was retained locally beside it
when the verified copy was promoted. Every live leg must require those two
local manifests to match and verify the aggregate manifest in full before
service startup.

## Restart justification and recovery boundary

The only reason this campaign is permitted is the ordered infrastructure
sequence: the original A1 suffered a real device-loss incident, then the first
post-reboot no-generation recovery gate aborted solely because an `ntfs3`
stdout evidence write triggered a filesystem/kernel failure. Neither event
provides candidate output, completed benchmark timing, output-quality evidence,
or a performance observation. This is not a performance-conditioned retry.

Before any campaign leg, the next distinct local-NVMe no-generation recovery
gate must pass. A1 is the first model generation after that gate. No candidate
or model-generation diagnostic is authorized before A1.

## Frozen treatment, order, and unchanged gates

The campaign ID is exactly
`w1-n128-nvme-recovery-abba-8936aac-c59aaad-20260723T131632Z`. The frozen
sequence is A-B-B-A:

1. A1 control: literal `VLLM_XPU_LAGUNA_M8_W1_N_TILE=64`;
2. B1 candidate: literal `VLLM_XPU_LAGUNA_M8_W1_N_TILE=128`;
3. B2 candidate: literal `VLLM_XPU_LAGUNA_M8_W1_N_TILE=128`, only after the
   unchanged phase-one gate passes; and
4. A2 control: literal `VLLM_XPU_LAGUNA_M8_W1_N_TILE=64`.

All original thresholds remain unchanged: 13 fixed unique prompts; at least
9/13 paired row wins; positive median paired change; at least `0.15 ms`
aggregate cycle saving; absolute acceptance-rate delta at most `0.001`; lower
candidate strictly beats lower control; and the eligible lower candidate
strictly exceeds `33.89498511171744 tok/s`.

All original exactness, cold-start, cache-zero, one-request-per-prompt,
no-warmup/no-reuse, long-then-next, rollover, accounting, source/runtime/model
identity, shutdown, idle, and cross-leg exact-token rules remain unchanged.
There is no performance-conditioned retry, rescue run, treatment switch, or
fifth run. Any pre-service tooling or infrastructure failure is preserved and
requires a new separately registered root; any failure after a measured leg
begins is classified and ends the applicable continuation under the inherited
rules.

## Frozen endpoint tooling boundary

The runner is the evolved
`tools/run_w1_n128_crossover_leg.sh`; the analyzer is the evolved
`tools/analyze_w1_n128_crossover.py`; and the live service entrypoint is
`tools/serve_laguna_nvme.sh`. The runner rejects ambient benchmark-sensitive
environment names before it sources the NVMe path helper, asserts the helper's
fixed constants equal the identity above, verifies the full model aggregate
manifest before service startup, and writes only under the active local-NVMe
artifact root.

The analyzer pins this preregistration, the runner, local model/artifact paths,
the local teacher/formal/counter evidence, and the unchanged promotion gates.
Tooling validation may parse artifacts but must not start a service or generate
a prompt.
