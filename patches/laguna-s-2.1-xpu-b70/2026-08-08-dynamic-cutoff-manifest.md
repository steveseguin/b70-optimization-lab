# Laguna dynamic DFlash cutoff source manifest

Date: 2026-08-08 America/Toronto

Status: default-off, device-rejected candidate. The corrected retry completed
but failed the pinned exact-token oracle; there is no promotable result.

## Source identity

- worktree: `/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731`;
- prerequisite: `561698049656690a55ea0ca9826dceba0e33a9c7`;
- initial candidate: `ae15e59d4d6ab67912de69011e6e5dd1ce2ce4b6`;
- corrected candidate: `00c8bbbb5c950abc69a27a2e733330652eece478`;
- branch: `experiment/laguna-shared-elementwise-m12-20260731`.

## Preserved artifacts

- thin bundle:
  `vllm-laguna-dynamic-cutoff-ae15e59d4-20260808.bundle`;
- bundle SHA-256:
  `678c5aea8230264443d9d4ef2d329fbb4b4364b270eb6aef45dcd3fede52fd88`;
- review patch:
  `0001-xpu-add-guarded-Laguna-context-cutoff-graphs.patch`;
- patch SHA-256:
  `54f34ce64b42cb2a89788e295c4b9e96cd8b3992f1ea6557ca9dd647860fa21e`.

The first device smoke exposed a field-name mismatch in the M1 prefill guard.
The preserved correction is:

- superseding thin bundle:
  `vllm-laguna-dynamic-cutoff-00c8bbbb5-20260808.bundle`;
- bundle SHA-256:
  `a1f0025bf9bd7cfe06e5e565ce48683258b08b119ebd6fc7c71873b6a0de5510`;
- incremental patch:
  `0001-xpu-use-InputBatch-prompt-length-in-cutoff-guard.patch`;
- patch SHA-256:
  `3df42c0d556bbdb7ae433707966266984f4081cbb2bb432283819c461ed0c732`.

`git bundle verify` passed for both bundles on 2026-08-08. The superseding
bundle contains both source commits and requires the prerequisite above.

## Offline evidence

- 27 focused cutoff/eligibility worker tests passed;
- 4 scheduler budget and empty-draft handoff tests passed;
- 15 Laguna model graph-contract tests passed;
- 5 collective tests passed, including all 96 gathers at both M1 and M12 and
  first-capture truncation rejection;
- Ruff passed on every modified source/test file;
- independent read-only review found no remaining correctness blocker for the
  bounded exact-oracle device gate.

The associated preregistration is
[`2026-08-08-dynamic-dflash-context-cutoff-preregistration.md`](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-08-08-dynamic-dflash-context-cutoff-preregistration.md).

## Device disposition

- attempt A:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/20260808-dynamic-cutoff-transition-a`;
  rejected source failure before M1 execution, clean shutdown/no device error;
  `bench.json` SHA-256
  `8eee4c037654cf405fab88b8f27220990bb023aa62a7cf036bbee52542990799`,
  `server.log` SHA-256
  `d82a159835ab3f72047acb70617f41479fc23d086f9de8c23c94b4a4fc0bd876`;
- attempt B:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/20260808-dynamic-cutoff-transition-b`;
  completed 128 tokens, exact oracle failed from output index 96, clean
  shutdown/no device error; `bench.json` SHA-256
  `a26099804f15c165d0287ed6d09fb7754ee63ba188ba82e5e5065d3e6a9b6b33`,
  `server.log` SHA-256
  `ab8a3bb0a6f03fb2b32e7271d93c22e49f97668cb5a0d6ee5c8b0ac5f9437d0e`.

Attempt B captured M1 on all four ranks but emitted no audited M1 replay line.
Its benchmark status is `FAIL`; its measured timing is not promotable.
