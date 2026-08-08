# Laguna dynamic DFlash cutoff source manifest

Date: 2026-08-08 America/Toronto

Status: default-off candidate; offline review complete, no device result at
snapshot time.

## Source identity

- worktree: `/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731`;
- prerequisite: `561698049656690a55ea0ca9826dceba0e33a9c7`;
- candidate: `ae15e59d4d6ab67912de69011e6e5dd1ce2ce4b6`;
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

`git bundle verify` passed on 2026-08-08. The bundle contains the candidate
branch head and requires the prerequisite above.

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
