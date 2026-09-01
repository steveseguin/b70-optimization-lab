# Qwen3.8 Flash-Next FP8 experimental snapshot — 2026-08-31

Status: **public research preview; not promotion- or deployment-qualified**

This snapshot is the passive publication boundary for the ongoing
Qwen3.8 Flash-Next FP8 work. It points to the exact retained artifacts needed
to inspect or eventually replay the best measured profiles without copying
active experiment files into a second, drifting recipe.

## What the evidence supports

| Profile | Scoped measurement | Evidence boundary |
| --- | ---: | --- |
| TP4/EP4, eager, MTP4, configured 512 | **20.727176 tok/s** median after first text | Fastest short research screen; repetitive p146/o256/c1 workload, Grade C, not the fixed realistic final gate |
| TP4/EP4, eager, MTP3, exact active 4K | **15.501565 tok/s** median after first text | Preferred practical 4K screen; median TTFT 187.899 s and wall output 1.246260 tok/s |
| TP4/EP4, eager, MTP3, p4096/o128 | **4.669548 tok/s** conventional 99-interval decode | Formal exact-depth fixture paired with the 4K profile above |

The August 30–31 target-side optimization work also does not supersede this
snapshot. It retains a target-only short frontier of `5.515783 tok/s`; later
component and endpoint experiments have not produced a higher qualified
Flash-Next result.

## Fastest short-screen identity

The MTP4 receipt is
[`20260827-tp4-mtp4-512-attempt1-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp4-512-attempt1-result.json).
It records:

- model `Qwen/Qwen3.8-Flash-Next-FP8` at revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- four Intel Arc Pro B70 32-GiB cards, TP4 and EP4;
- native MTP4 with four speculative tokens;
- eager execution, graph off, one active sequence, and prefix caching off;
- `max_model_len=512`, `max_num_batched_tokens=64`, BLHNC KV layout, and
  `282427392` KV-cache bytes;
- `enable_thinking=false` and no diagnostic flags;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- loaded native runtime built at
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- selective UVA placement of the PLE n-gram and input embeddings,
  `13,117,911,040` host-resident/GPU-addressable bytes per rank.

All 26 bounded MTP0 comparisons matched, the fixed-set repeat was stable
16/16, the small cache-zero needle passed, and all 24 audited requests had no
cache reuse. The inherited non-thinking target scored 5/7 literally, or 6/7
under the packet's semantic reading. The three speed rows span 12.27% of their
median. The receipt explicitly marks the result `promotion_eligible: false`.

## Preferred exact-4K identity

The MTP3 receipt is
[`20260827-tp4-mtp3-4352-attempt1-result.json`](../../experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-4352-attempt1-result.json).
It uses the same model, source, staged runtime, TP4/EP4, eager mode, graph-off
execution, and selective host placement, with:

- three speculative tokens;
- configured maximum length 4,352;
- one active sequence and 64 maximum batched tokens;
- 25 fixed cache blocks and `294195200` KV-cache bytes;
- BLHNC KV layout and prefix caching disabled.

It matched all 26 sealed MTP0 comparisons, repeated 16/16, passed the exact
cache-zero 4K needle, and completed the formal exact-depth gate. It remains
Grade C: the MTP3 official-thinking transfer later stopped during its repeated
session, and clean-host/deployment qualification is still open.

## Closed reproduction inputs

The surrounding directory already contains the durable reconstruction inputs:

- [`model-contract.json`](model-contract.json) and
  [`verify-model.py`](verify-model.py) freeze and verify the 185.56-GB model
  tree;
- [`prepare-sources.py`](prepare-sources.py) reconstructs the measured vLLM
  and XPU-kernel source trees from the certified patch series;
- [`runtime-contract.json`](runtime-contract.json),
  [`runtime-stage.sha256`](runtime-stage.sha256),
  [`prepare-runtime.py`](prepare-runtime.py), and
  [`publication-readback.json`](publication-readback.json) bind and install
  the publicly hosted 18-file native runtime;
- [`dependency-contract.json`](dependency-contract.json),
  [`requirements-runtime.lock`](requirements-runtime.lock),
  [`pip-freeze-observed.txt`](pip-freeze-observed.txt), and
  [`wheelhouse-contract.json`](wheelhouse-contract.json) preserve the observed
  Python environment and its unresolved portability boundary;
- the [certified source patch packet](../../patches/qwen38-flash-next-fp8-b70/README.md)
  owns the exact source deltas;
- the [result packet](../../results/qwen38-flash-next-fp8-b70/README.md) owns
  the full matrix, negative results, quality limits, and chronology;
- the [MTP4 experimental launcher](../../experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp4-512.sh)
  and both structured receipts above retain the origin-host launch and run
  identities.

This is enough to inspect the complete identity and reconstruct the model,
source, and hosted native stage. It is intentionally **not yet enough for a
safe clean-host launch**. The 177-package environment lacks a complete
hash-addressed wheelhouse, portable four-card topology/preflight work remains
open, and the reconstructed artifacts have not completed a fresh artifact-only
startup replay. Accordingly, `preflight.sh`, `run-server.sh`, `quality.sh`,
and `stop.sh` remain fail-closed placeholders.

## LocalMaxxing disposition

**Withheld.** No submission was made from this snapshot. The 20.727 tok/s row
uses a narrow repetitive screen rather than the fixed varied-prompt 512-cap
final gate; the MTP path lacks full quality/repeated-session qualification;
and there is no hash-bound promotion attestation or clean-host replay. These
gaps make the result useful for neural.download research visibility but
ineligible for LocalMaxxing.
