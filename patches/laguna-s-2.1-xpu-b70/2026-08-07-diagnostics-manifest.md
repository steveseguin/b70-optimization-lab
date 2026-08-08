# Laguna August 4-7 diagnostic source manifest

Status: preserved diagnostic history, not a promoted runtime or result.

The active vLLM worktree was
`/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731`. The preserved
range starts after record selector commit `1a7f61fef` and ends at
`561698049656690a55ea0ca9826dceba0e33a9c7`. The measured XPU-kernel source
remained `99886d783372e621941228250091dc8ebdc1595d`.

## Bundle

- `vllm-laguna-aug04-07-diagnostics-561698049-20260807.bundle`
- prerequisite: `1a7f61feffbc61b21b73f812d231c7426386ccdc`
- head: `561698049656690a55ea0ca9826dceba0e33a9c7`
- SHA-256: `bf32a3ecfd95ef5f90f8c89c26ba051afcaabcc15ce0448e61ec62c4b0899284`
- `git bundle verify` passed on 2026-08-07.

## Review patches

| File | Commit | SHA-256 |
| --- | --- | --- |
| `0001-xpu-allow-breakable-graph-without-speculation.patch` | `63e904974` | `7f677aab33df3d2261ac45316e711200e810cbcdcb5b347055ac359ca7608080` |
| `0001-xpu-stop-forcing-eager-on-no-spec-decode.patch` | `63da5e0ea` | `b767e98d5f46e9f0d7bc71cf9b71ed849c801e1e5ee4638a697bbee7c76ca823` |
| `0001-xpu-replicate-laguna-attention-diagnostic.patch` | `8ed1012e9` | `21c1ae5c0f30b6b3ce0b5a00c475868cbdaea675adf5eef7a1cc3de0ce22b792` |
| `0001-xpu-fix-replicated-attention-gate.patch` | `945a554bf` | `a4eda0d71d720bbacdb13c213b26b6db799f147d71763ee02f8be0db120431cf` |
| `0001-xpu-generalize-native-attention-mm-width.patch` | `561698049` | `29630d92b0df6a352e2a2df354257803bd636d249e9e48931b2dc77c47622eb2` |
| `0001-laguna-self-derived-no-drafter-budget-audit.patch` | `3e15051e6` | `5f0b74492e293da64cafae0f44b12329bb34348e9cb8577d5d0db3fd256e9214` |
| `0001-laguna-expose-native-attention-mm-selector.patch` | `f306c0027` | `427d418341a0f5ff22ba8d06537efd97bf17b5773ad5f5a8c4853b131dd118b8` |

The `3e15051e6` patch is retained as tested history, but its check is
self-derived launcher evidence rather than an independent observation of the
runtime Scheduler ceiling. It must not be reused as the final scheduler proof.

## Primary evidence roots

- no-spec graph diagnostic:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/20260806-nospec-graphfix-e`;
- speculative 32K comparison:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/20260804-eventprofile-q12`;
- crossover attempts: `20260807-crossover-q12-*` and
  `20260807-crossover-nospec*` under the same run root;
- replicated-attention failures: `20260807-replattn-nospec-u80`,
  `20260807-replattn-nospec-u90`, and `20260807-replattn-pin3`;
- native-MM A/B: `20260807-attnmm-base` and
  `20260807-attnmm-attnmm`.

The graph diagnostic benchmark produced useful topology and throughput data,
but the overall runner exited 2 on the subsequently fixed scheduler audit, ran
without a canonical oracle, and differs from eager by 9/128 output tokens at
32K. It is diagnostic only.
