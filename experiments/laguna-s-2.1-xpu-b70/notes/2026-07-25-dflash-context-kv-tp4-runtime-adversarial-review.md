# Laguna DFlash context-KV TP4 runtime gate — adversarial source review

Date: 2026-07-25 America/Toronto

Status: **PASS. The fifth packet is cleared for execution.** This satisfies the
independent source and adversarial review that the
[TP4 runtime preregistration](2026-07-25-dflash-context-kv-tp4-runtime-preregistration.md)
requires before any XPU or model execution is authorized.

Reviewed: harness at main `e9182e125` (now `626052551`, see Observation A);
candidate source `7c38a2022` in
`/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725`.

Scope: ~3,010 lines across `run_laguna_dflash_context_kv_runtime_gate.sh`,
`run_laguna_dflash_context_kv_runtime_arm.py`,
`analyze_laguna_dflash_context_kv_runtime_gate.py`,
`create_laguna_dflash_context_kv_runtime_consumption.py`, and the analyzer test
suite, plus the 1,397-line candidate diff against record `ef334233d`.

## The three prior failure modes are closed

| Prior packet | Failure | Fix, verified |
| --- | --- | --- |
| `de35c566b` | frozen `PYTHONPATH` omitted the tracked gate-tools directory | line 309 sets `PYTHONPATH="$tools:$vllm:$kernels"` with the tools directory first, alongside `PYTHONSAFEPATH=1` |
| `f52f9e8ef` | refused an RPC directory stranded by the previous failure | both paths are refused at preflight (230-232) *and* again per-arm (280-281); each arm's directory is created immediately before that arm (282) and bound to `active_rpc` (283) **before** the worker and idle checks (285-288), so a mid-arm failure can no longer strand a precreated directory |
| `649f150cf` | `apply_model(function)` rejected function serialization | replaced by two named worker RPCs, `get_laguna_tp4_runtime_identity` and `arm_laguna_dflash_runtime_request_phase`. Neither accepts a serialized callable. Both fail closed unless five trace/evidence variables are set, both verify the target model class, the arming RPC is one-shot, and the identity RPC returns only rank/world/backend, local and TP rank, XPU device identity, and model class |

## The pass condition that matters most is genuinely enforced

Acceptance condition 7 — that the candidate dynamically witnesses workspace
execution and reuse while the control witnesses only the incumbent branch — is
the condition that separates "the gate passed" from "the optimization actually
ran". It is enforced as a dynamic per-rank witness, not a flag echo:

- the control arm must record `branch=incumbent`, and the analyzer dies on
  `control: workspace branch unexpectedly observed`;
- the candidate must record `branch=workspace` with a boolean `workspace_reused`;
- the first call at each context width must be `reused=False` and every later
  call `reused=True` with byte-identical workspace signatures, or the analyzer
  dies on `workspace identity drift`;
- **every rank** must show at least one request-phase call with
  `workspace_reused is True` (analyzer lines 1084-1090).

A candidate arm that silently fell back to the incumbent path cannot produce a
pass.

## Exactness and aliasing defences are adequate

The workspace uses uninitialized `torch.empty` buffers, so the material risk is
a partially rewritten buffer leaking deterministic stale data — which a single
32-token request could easily hide. That risk is closed by construction: the
workspace cache key includes device, dtype, `num_layers`, `num_ctx`,
`hidden_size`, `num_kv_heads`, and `head_dim`, so a reused buffer always has
exactly the shape it was created for, and each cycle rewrites every element
(`rms_norm` full-width, `torch.bmm` with `out=`, then a full `copy_`).

Additional guards, all verified present: a self-aliasing check at creation, a
`validate()` identity-drift check on every reuse, an explicit check that no
workspace pointer aliases the inputs or weights, a refusal if weights change
after any workspace use, and a stream-capture check.

## Harness structure

`set -euo pipefail`, `set -f`, `umask 077`, frozen `PATH`, `env -i` per arm with
private HOME/TMP/cache/XDG roots. Dirty-tree assertions on all three
repositories (205-211). Seven pinned artifact hashes plus four native binaries.
Worker and idle assertions before and after each arm, and again before analysis.
Evidence and final manifests sealed, then `chmod -R a-w`.

Ordering verified: **every hash check (213-224) precedes marker consumption
(269)**, so artifact drift aborts cleanly without spending the packet. The
marker itself is created `O_CREAT|O_EXCL|O_NOFOLLOW` with `fsync` of both the
file and its parent directory.

The analyzer's `main()` is straight-line with no permissive branch and no
exception swallowing; `die()` raises and the shell's `set -e` converts a
non-zero analyzer exit into a failed run. Its test suite passes **33/33**.

## Observations — not blockers

**A. The packet identity moved during documentation work.** `main_commit` is
`git rev-parse HEAD` of this repository and is embedded in `identity.txt` and
the marker filename. Documentation commits made on 2026-07-25 advanced HEAD from
`e9182e125` to `626052551`. No gate tool, candidate source, or pinned hash
changed, so this review applies unchanged, but the packet that will execute is
the one at main `626052551`.

**B. The one-shot guarantee is procedural, not cryptographic.** Because the
marker is keyed on `(main HEAD, identity.txt hash)` and `identity.txt` contains
the main commit, any unrelated commit mints a fresh identity for a byte-identical
harness. This is consistent with the stated workflow that a new commit is a new
packet requiring new review, but it does not by itself prevent re-running a
failed harness after an unrelated commit. Worth stating explicitly so the
"terminal" property is understood as discipline rather than enforcement.

**C. Shape coverage is narrow by design.** The gate runs one request of 32
tokens, so only the context widths that request exercises are proven, and the
workspace is keyed per shape. Exactness at other widths is not established here.
This is consistent with the preregistration, which authorizes only the *design*
of a follow-on crossover — but that crossover must not assume broad shape
coverage from this gate.

## Verdict

Cleared to mint a fresh `O_EXCL` marker and execute. Preconditions confirmed at
review time: four B70s idle at 43 MiB, no vLLM or torchrun processes, all three
worktrees clean, weights present on NVMe, teacher hash matching
`d41d3d5e2471ee98`.

A pass still authorizes only the design of a separate preregistered cold
graph-vs-graph crossover. It is not a record claim, a payload, or a submission.
