# AMD transfer tests: exact but neutral dispatch; startup incident

No new optimization was promoted. The bounded transfer test preserved the
preferred official Qwen3.8 27B FP8 target, measured its existing service at three
input lengths, and rejected a dispatch change that did not reduce elapsed time.
The combined newer-runtime/V2/DFlash2 candidate never became ready. The computer
froze during startup and the user restarted it. Its cause remains unknown.

The original qualified FP8/MTP1 service was restored and passed post-reboot
checks: all 12 strict outputs and all 18 measured continuations match the
pre-incident control exactly. `CURRENT.md` owns live service state.

## Measured original control

Two Intel B70s, official FP8 weights, FP16 activations and KV, fixed MTP1,
one active user, 33,024 total-token capacity, 4,096 scheduling budget, prompt
caching off. This is the current package launcher's configuration, not the
older 4,096-capacity reading-speed profile or historical MTP5 decode record.
The complete launch environment is in the evidence archive.

| Actual input tokens | Reading speed, input tokens/s | HTTP first-token wait | Writing speed, output tokens/s |
| ---: | ---: | ---: | ---: |
| 512 | 2,858.80 | 0.1906 s | 52.98 |
| 2,048 | 3,676.93 | 0.5661 s | 54.86 |
| 16,384 | 3,305.14 | 4.9691 s | 56.13 |

These are pre-incident control measurements: three input classes (prose, code,
documentation), two repeats each at each exact length, 18 measured requests and
three separate warmups. Each class combines distinct source files once; the
corpus does not fill context by repeating a short sentence. All requests report
zero cached tokens and complete 128-token outputs repeat exactly.

Reading speed is actual input tokens divided by server prefill duration, from
first scheduled execution to first token, reconstructed from server histogram
deltas. HTTP wait is measured separately. Values use the median within each
class, then the median across classes. Writing speed here uses the 99 intervals
between output tokens 1 and 100, but the forced 128-token continuations are a
screen, not a new realistic-suite decode headline. These points do not establish
retrieval accuracy or performance at unmeasured context lengths.

The separate full 12-prompt, six-class natural-completion suite passed its
workload and canary gates, matched all 12 complete qualified-reference token
arrays, and measured **54.8547 output tokens/s**. Its difference from the older
54.8176 reference is ordinary baseline variation, not an optimization gain.

## Independent process after the user reboot

The restored original service passed its full workload/canary suite at
**54.3158 output tokens/s**, 0.98% below the earlier control, with all 12 complete
token arrays identical. This is same-recipe recovery support, not a matched
candidate comparison. The new server repeated all three context lengths:

| Actual input tokens | Reading speed, input tokens/s | HTTP first-token wait |
| ---: | ---: | ---: |
| 512 | 2,877.61 | 0.1916 s |
| 2,048 | 3,681.84 | 0.5653 s |
| 16,384 | 3,313.21 | 4.9580 s |

All 18 measured continuations matched the pre-incident complete outputs;
warmups are separate and cached tokens remain zero. Reading rates differ by
less than 0.7% at each measured length. The archive includes both sessions,
individual measurements and restored strict/context monitoring windows.
Neither baseline session is an optimized candidate or an exhaustive stability
test. The service remains running under its persistent helper.

## Transfer decisions

The [AMD source review](../../../community/1337hero-r9700-qwen38-radiance/README.md)
separates the reported eight-user aggregate from single-user output speed and
records its code-heavy, high-acceptance workload. Aggregate concurrency is a
valid metric when labeled, but it cannot replace single-user latency or prove
that a draft generalizes. Our local tests did not reproduce that AMD result.

| Approach | Local test and disposition |
| --- | --- |
| Combine projection dispatches | A small C++ dispatcher invokes the unchanged FP8 QKVZ and FP16 BA operations. All 12 tensor cases/repeats match exactly. No wall-time benefit; rejected before wider testing. |
| Packed GDN execution | Already present in the accepted 27B stack. The serial Python-to-C++ opportunity from another model is not a new gain here. |
| Weight permutation / matrix layout | Reviewed, not applied. Changing layout can select a different oneDNN arithmetic path; no qualified equivalent was established. |
| Deeper convolution/GDN fusion | Not implemented. Larger engineering work, and matrix GEMMs remain the main measured prefill cost in the prior profile. |
| DFlash2 K7 with newer upstream and V2 | Source integration prepared and one startup attempted; host froze before readiness. No inference, quality, acceptance, speed or long-context result. Unsafe to retry unchanged. |

The projection screen used production-shaped synthetic tensors, both output
arrays, random/zero/alternating-sign inputs, independent control recomputation,
weight/input immutability checks, and five alternating ABBA/BAAB timing blocks.

| Rows | Control wall time | Candidate wall time | Candidate latency change |
| ---: | ---: | ---: | ---: |
| 1 | 75.5769 microseconds | 75.6094 microseconds | +0.0430% |
| 2 | 76.7686 microseconds | 76.7684 microseconds | -0.0003% |

Host submission alone fell about 22–23%, but synchronized elapsed time did not.
The preregistered gate required at least 3% wall savings at both row counts.
No larger row sweep, model integration or claimed end-to-end gain followed.
The idea of reducing dispatches came from Radiance's RX3 projection work; this
local prototype does not copy its implementation or quantization changes.

## Freeze and restoration

The candidate used the September 14 XPU nightly, upstream
`dc36fcce902a63eab06c1b93a5c4a5ee178a0c56`, with reviewed accepted FP8 overlays,
the V2 runner and pinned tcclaviger DFlash2 FP8 drafter
`ee0cb26a8279b7910cc28d82a8a3e15e4728d56f`. Torch/native-library identity checks
passed before reuse; those checks do not establish server runtime safety.

The candidate started at 09:26:56 EDT. Its last server entry at 09:27:48 was
in target construction/loading; the previous kernel journal ends at 09:27:55.
There is no completed target-load, draft-load or generation receipt. The user
reported a freeze and manually restarted the host; the new boot began at
11:08:33 EDT. A later startup-timeout marker is preserved, but the controller
did not produce a timely clean-stop receipt during the freeze.

The journal contains no specific GPU fault or OOM before it stops. Docker's
post-reboot exit 255 and `OOMKilled=false` do not establish a cause or exclude
memory pressure. The V2 loader initializes the target before loading the draft,
so attributing this to DFlash kernels would be unsupported. A read-only loader
comparison found no concrete regression. The KMS framebuffer warning in the new
boot is recorded separately and does not diagnose the previous freeze.

The failed image `sha256:3be4c6c9918c820b508e3c13fcfd04323e53a96177ac0de0eb6b1179ee45760f`
is rejected explicitly by the candidate launcher, even with a new output root.
The root `FAULT.json`, stopped container, logs and cache are preserved. There
was no agent reboot, driver reset, host power/swap/page-cache setting change or automatic
retry. Both GPU compute checks and XCCL passed once after the user's reboot,
with no new kernel faults in that check window. Recovery admitted only the
original qualified R304 service and its verification requests.

## Evidence and remaining work

- [Preregistered gates](2026-09-14-amd-transfer-prereg.md).
- [Machine-readable results](../data/2026-09-14-amd-transfer/summary.json),
  [hash manifest](../data/2026-09-14-amd-transfer/manifest.json),
  [raw evidence archive](../data/2026-09-14-amd-transfer/evidence.tar.gz).
- [Freeze receipt](../data/2026-09-14-amd-transfer/freeze-incident.json) and
  [loader source review](../data/2026-09-14-amd-transfer/incident-loader-source-review.json).
- [Projection prototype and method](../probes/amd-transfer-projection-dispatch.md),
  [DFlash2 integration review](2026-09-14-amd-dflash-feasibility.md),
  [quarantined source overlay](../docker/amd-transfer-20260914/README.md).
- [Evidence collector](../scripts/collect-amd-transfer-evidence.py) replays the
  raw timing/output evidence and verifies archive hashes without GPU work.

No concurrency or DFlash2 long-context claim can be made from this campaign.
The current defaults and historical speed records remain unchanged. Any future
new-base/V2 work first needs a concrete stability diagnosis or changed startup
approach; the unchanged failed launch is closed. No further GPU candidate sweep
is warranted during this recovery session. The repository pin audit still reports
231 historical Flash-Next tooling drifts; those unrelated frozen pins were not
rewritten.
