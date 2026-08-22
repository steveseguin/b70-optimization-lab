# Qwen3.8 MTP5 Q64xK32 endpoint integration preregistration

Date: 2026-08-21

Status: **complete and stopped terminal at b1**: arm a1 (stock control)
passed everything at `100.928359 tok/s` conventional, but the candidate
server failed engine-core initialization — the operator-qualified DSO lacks
the full chunk-prefill configuration farm (0.6 MB versus the stock 1.5 GB)
and is not endpoint-deployable as built. No b2/a2 ran; no same-root retry.
See the [endpoint2 result](2026-08-21-qwen38-mtp5-q64k32-endpoint2-result.md).

## Bounded question

On the four-B70 measuring host's post-recovery margin-free MTP5 TP2 lane
(GPUs 2,3), does substituting the qualified Q64xK32 chunk-native
FlashAttention stage for the incumbent stock stage improve the full-25
cold-suite decode rate, with unchanged lane identity and explicitly reported
exactness accounting?

Basis: the
[r3 operator qualification](2026-08-21-qwen38-mtp5-m6-fa-q64k32-abba-r3-result.md)
(`74.68`/`74.96 us/call` paired KV1300 saving on GPU2/GPU3, ~1.2 ms per
target step across the 16 full-attention calls). Expected endpoint effect is
roughly +2.5-3% over the `~101 tok/s` research anchor; this campaign
measures it honestly rather than assuming it.

## Design

Four fresh-server arms in A-B-B-A order on the identical lane identity used
by the A2/B2 composite pair (same model manifest fail-closed direct+cached
verification, sealed compile-cache contract, pad-on engagement per rank,
25-prompt suite, cache-zero, fresh roots):

- **A1/A2 (control):** `STAGE=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820`,
  device DSO `604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c`,
  `VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY=0`, and no log line containing that
  variable name on any rank.
- **B1/B2 (candidate):** `STAGE=/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2/runtime`,
  device DSO `01a5b35b5a9c6321b436b137f95403db9e45ce4aabb44257dc7e4f45c84aecf5`,
  `VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY=1`, and exactly one
  `VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY engaged` stderr line per rank.

Shared stage identities (extension, Python interface, stock DSO) must match
the sealed values on both stages
(`33938cdd…`, `869c79f5…`, `3cbd3ed2…`); candidate arms verify the candidate
20-file graph manifest
(`d662dba3927fac706ff221902f536b67178b6875f66604597a1f2fe98a4defc4`),
control arms the stock manifest
(`47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`).
Every arm additionally proves the loaded device DSO in each rank's
`/proc/<pid>/maps` (canonical path + SHA), so a stage-selection error cannot
be misattributed to the policy.

## Metrics, exactness accounting, and gates

Primary: per-arm full-25 preferred median (and legacy median as helper),
paired A-B-B-A central delta with a 10,000-resample hierarchical bootstrap
(resample arms, then prompts within arms).

Exactness accounting is **reported, not gated at 25/25**, because the
incumbent lane's own A/B parity is 21-22/25 under every closed terminal
preregistration: each arm records complete `output_sha256s`; the packet
reports B-vs-A parity counts, candidate-vs-fresh-target-oracle counts, and
flags any catastrophic family (e.g. all-zero streams) as an immediate
campaign stop. Arm A1 must pass the lane's standard quality gate battery
before B1 is allowed (same rule as the composite pair); B1 must pass the
same battery before B2.

Decision: the candidate is endpoint-confirmed only if the paired central
delta is positive with a 95% lower bound above zero and no arm shows a
quality-gate failure or catastrophic family. Regardless of speed, nothing
here is promotable to a record or LocalMaxxing: the lane's runtime
nondeterminism remains open, and any promotion path still requires its own
campaign under the lane's full standards.

## Frozen artifacts (placeholders until the driver derivative is reviewed)

- endpoint driver
  `scripts/run-20260821-qwen38-mtp5-q64k32-endpoint-abba.sh`:
  `849d4b6cc4287b7cb392ef983598c1fd930b8f7566edcb90bb09d9243093d5c8`
  (mode 0755). It verifies both stage trees per-file each invocation,
  refuses existing arm roots, requires clean `main == origin/main`, and
  regates every predecessor: runner exit 0, sealed-gate pass (with
  `--require-quality-pass` for the a1->b1 and b1->b2 edges), artifact
  checksum set intact, produced-by-current-bytes, and the predecessor's
  own role marker count before any successor may start.
- underlying arm runner
  `experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh`
  at `49ee2736420f0287fb72bc71a00c9a363a8487ce14555c623bbdc0dc13c6eff7`:
  extended by two reviewed hunks: the first maps
  `VALIDATION_FA2_M6_HEAD256_Q64K32_POLICY` to an explicit
  `VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY={0,1}` export (controls receive
  an explicit `0`), so the `env -i` whitelist cannot silently drop
  operator intent; engagement is separately proven by the marker gate
  (candidates: exactly two `... engaged` server-log lines; controls:
  zero); the second adds the two new `VALIDATION_` names to the runner's
  sealed-mode allowlist, whose fail-closed rejection of the unlisted
  names was demonstrated live before any arm root existed (the a1 label
  was not burned: no root was created).
- result roots (must not exist before launch):
  `/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-q64k32-endpoint2-{a1,b1,b2,a2}-20260821/`.
  The original `endpoint-a1` label burned on a pre-launch false start: the
  sealed identity gate refused a non-empty vLLM source diff
  (`66f5823c...`, two uncommitted Codex-era WIP files, preserved to
  `patches/vllm-codex-wip-preserved-20260821/` and stashed in-tree before
  the tree was restored to an empty diff). That root contains only
  pre-launch scaffolding, no GPU or model work, and is preserved unused.

Launch requires: clean `main == origin/main` including the frozen revision
of this note; quiet kernel journal; no other model workload, benchmark, or
AOT build on any card; all frozen hashes rechecked immediately before
the single launch; stop on first arm failure with no same-root retry.

## endpoint3 addendum (2026-08-22)

The [r4 requalification](2026-08-22-qwen38-mtp5-m6-fa-q64k32-abba-r4-result.md)
qualified the integration DSO. This preregistration's design carries over
unchanged for **endpoint3** with only these recorded identity updates in the
same driver (now
`d9a8409f10f17814f3203ec300cd9b6129de37391f0476f78174253d9b1b570e`):
candidate stage `…attn-override-20260821-r3/runtime`, candidate device DSO
`979e91c1f11d9e6ede77c494803889e9f47dd881c2d02e1c290c5246c0dbb616`,
candidate graph manifest sha `0642e029…`, labels
`qwen38-q64k32-endpoint3-{a1,b1,b2,a2}-20260822`. Same gates, same order,
same stop rules; single sequential launch authorized after push.

## endpoint3 stop and endpoint4 relaunch rule (2026-08-22)

endpoint3 stopped invalid at its stock control a1: bench row 6
(`selection--sql-debugging`) generated only 58 tokens — the lane's
documented stochastic early-EOS family on that prompt (the M1 microscope
saw 68) — so the strict 100-token metric window correctly refused the arm.
This is a data-validity stop, not a performance or correctness result; the
24 valid rows medianed on-anchor and are not quotable. Root preserved.

**Bounded relaunch rule, preregistered now:** a campaign attempt stopped
solely by this known stochastic short-family data-invalid may be relaunched
once as a fresh campaign with fresh labels and unchanged bytes. At most two
such relaunches total (endpoint4, endpoint5); a third occurrence closes the
campaign design as blocked on the lane's prompt-6 nondeterminism and
requires a redesigned suite or metric preregistration. endpoint4 labels:
`qwen38-q64k32-endpoint4-{a1,b1,b2,a2}-20260822`; driver refrozen at
`f9d67d1c2226713c637eaec82f50a980411c16be371daa86f83f113f9df1f118`.
