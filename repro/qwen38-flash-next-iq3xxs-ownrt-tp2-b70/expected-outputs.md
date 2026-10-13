# Expected 128-token outputs

Each output is the complete 128-token array in the linked CPU oracle. Hashes below are the sealed submission output hashes; verify.py compares token arrays directly and recomputes timings.

| Prompt | Oracle token IDs | Submission output SHA256 | 99-interval tok/s |
| --- | --- | --- | ---: |
| incident-retrospective | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/incident-retrospective/result.json) | `566a9aa7831b695ab28efc3a6503e7dea56ad130ac0ecae723697fbeaacf20e6` | 37.456788 |
| code-review | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/code-review/result.json) | `f862f3d2409abd4a2da319167f88b5727c18df04cf7d428eba5e50121ff23d78` | 35.245961 |
| customer-email | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/customer-email/result.json) | `83eba74b039b972fd1b7a71db1c70cd28d03284073b899847997daa023a07daa` | 36.539922 |
| sql-debugging | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/sql-debugging/result.json) | `60ecf13b8b451fb8d30db102455abc5cb2e7a2ac6b32395523046441f106037c` | 36.979068 |
| release-plan | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/release-plan/result.json) | `d3f774416e186779e835445e8cba391336be11643897eb742c9ed1d5aaaa4f5a` | 37.752601 |
| benchmark-analysis | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/benchmark-analysis/result.json) | `c8775f1f45ee5491fdb7568239332b7144802552a4eb3f4cd23adbd1c6716388` | 37.780508 |
| architecture-tradeoff | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/architecture-tradeoff/result.json) | `d4f62000688ad7a8e936ea21806cde07abb5f248ccab0d5576f2b83c526361e4` | 39.605007 |
| bug-report-synthesis | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/bug-report-synthesis/result.json) | `77776c0c0bb1b6b8744172c77334f8d0873cf6910054f72cc96f289514d504e4` | 35.262651 |
| technical-guide | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/technical-guide/result.json) | `e57101247696e21635ba95729a0c0f430e8e3e6691aded06bdd1c7bf4473cecc` | 37.824960 |
| risk-register | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/risk-register/result.json) | `1ae0241be4819357c105a94b805cb17edada4b6d07ff64d6e85f8ec77a421892` | 38.699972 |
| performance-hypotheses | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/performance-hypotheses/result.json) | `a2476c7267f011ffe317bbcc40a57bd6303897ed8d981c5b5080798e57b537b8` | 38.605777 |
| decision-memo | [result.json](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/decision-memo/result.json) | `8e9381da14728b8fa674a4c1a31eb154c275e73f64dbb65618bcd34bf111da2a` | 39.235215 |
