# Qwen3.6 27B FP8 native TP2 Docker on 2x B70

Community contribution from [PR #9](https://github.com/steveseguin/b70-optimization-lab/pull/9).

## Classification

| Field | Value |
| --- | --- |
| Evidence level | **`B70-tested`** — recipe runs here at 30.171 tok/s median decode, inside the contributor's reported range |
| Patch review status | Read in full; recipe executed here 2026-07-25 |
| Tested in reference lab | Yes — full TP2 serve path plus 15-row throughput measurement |
| Safe to merge as documentation | Yes — merged 2026-07-25 |
| Eligible for `repro/` or `results/` | Not yet; see Disposition |

Merged into `main` as a community submission and relocated into this directory.
The contributed recipe is not present in `repro/` and its claim is not in the
promoted ledger; the only ledger reference is the Community-Reported row in
[`results/README.md`](../../results/README.md).

The contribution is documentation only: two Markdown files, no code, no CI, no
workflows, no external URLs, no secrets, and a pinned official Intel image.
Nothing in it executes on merge. The reservations below are about evidence
quality and copy-paste safety, not about malicious content.

## Provenance

- Contributor: `dominick253` (GitHub association NONE, first contribution)
- Source: PR #9, 3 commits `de8dec51e`, `8a94f466a`, `72e08ff2f`
- Right-to-submit statement: implicit via `CONTRIBUTING.md`; not separately stated
- Third-party material: none beyond the public `intel/llm-scaler-vllm` image

## Claim

The contributor reports a working TP2 Docker deployment of `Qwen/Qwen3.6-27B`
at native FP8 across two Arc Pro B70s under `intel/llm-scaler-vllm:0.21.0-b1`,
tested 2026-07-22, and reports 28.3-34.7 tok/s across five prompt lengths at
256 output tokens. The PR's `results/README.md` row summarized this as
"Speed-benchmarked 34 Tokens a second".

This is the contributor's claim on the contributor's hardware. It is not a lab
measurement.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2x Intel Arc Pro B70, VRAM unstated |
| OS / kernel | **unknown — not supplied** |
| GPU driver (`i915` / `xe`) and version | **unknown — not supplied** |
| compute-runtime / level-zero | **unknown — not supplied** |
| Engine / image | `intel/llm-scaler-vllm:0.21.0-b1` (pinned) |
| Model repo and revision | `Qwen/Qwen3.6-27B` @ `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9` |
| Quantization | weights native FP8 (`--quantization fp8`); KV `fp8_e4m3`; dtype `float16` |
| Command and environment | Supplied in full; see the contribution README |
| Prompt / output / context | Prompt ~10-2000 tokens, output 256, `--max-model-len 262144`, `--max-num-seqs 4` |
| Cache and speculation policy | `--no-enable-prefix-caching`; no speculation; cold/warm state **unstated**, `cached_tokens` **not reported** |
| Metric definition, repeats, dispersion, TTFT | Prefill time given; metric definition, repeat count, and dispersion **unstated** |
| Logs / JSON / durable links | **none supplied** |

The three unknown host-identity rows are the first thing to request. They are
also exactly what the failed reproduction below needs in order to be
interpreted.

## Reference Lab Environment

| Field | Value |
| --- | --- |
| GPUs | 4x Intel Arc Pro B70, BDF `0000:23:00.0`, `0000:27:00.0`, `0000:43:00.0`, `0000:47:00.0` |
| Kernel | `7.0.0-28-generic` |
| GPU driver module | `xe` |
| Host compute-runtime / level-zero | `intel-opencl-icd` and `libze-intel-gpu1` `26.18.38308.1-0` |
| Container runtime | podman 4.9.3, rootless (installed 2026-07-25 for this validation) |

## What Was Actually Run Here

Two things, on 2026-07-25:

1. A bounded multi-GPU Level Zero context probe
   ([`validation/probe-multigpu-context.sh`](validation/probe-multigpu-context.sh)),
   scoped to the reproduction failure reported in the PR discussion.
2. The contributed recipe itself
   ([`validation/validate-recipe.sh`](validation/validate-recipe.sh)), served
   on cards 0 and 1, followed by a 15-row throughput measurement
   ([`validation/bench-recipe.py`](validation/bench-recipe.py)).

`Qwen/Qwen3.6-27B` was downloaded at the pinned revision
`6a9e13bd6fc8f0983b9b99948120bc37f49c13e9` and verified at 29 files /
55,586,107,940 bytes with no incomplete blobs.

### Deviations from the contributed command

All deliberate, all recorded in the script header:

| Deviation | Reason |
| --- | --- |
| podman (rootless) instead of docker | No docker on the reference host; same pinned image |
| `--device=/dev/dri --group-add keep-groups` instead of `--privileged` | The probe proved `--privileged` unnecessary; it was not granted |
| `--host 127.0.0.1` instead of `0.0.0.0` | The contributed command publishes an unauthenticated endpoint on every interface; this lab will not |
| Model path from the local HF cache | The contributed `/home/dom/...` path cannot work for anyone else |
| `--shm-size` dropped | podman rejects it together with `--ipc=host` |

Quantization, dtype, KV dtype, context length, block size, `max-num-seqs`,
memory utilization, eager mode, prefix caching, parsers, and the generation
config overrides were all exactly as contributed.

### Measurement method

One request in flight at a time, so this is single-session decode and never
aggregate. Prompts are freshly generated per row and per pass, calibrated to
target length against the server's own `/tokenize` endpoint. A warmup request
is issued and discarded. Three full passes over the contributor's five prompt
lengths at 256 output tokens each, giving 15 measured rows.

## Findings

A second contributor (`bosd`) reported in the PR that the recipe fails on their
2x B70 host in two ways: TP2 startup dies at
`urContextCreate(.DeviceCount = 2) -> UR_RESULT_ERROR_UNKNOWN` inside
`torch.xpu.device_count()`, with device enumeration itself succeeding; and a
TP1 fallback serves but generates at roughly 0.5 tok/s. They attributed both to
the container's compute-runtime `26.14` being older than a host on the `xe`
driver, kernel `7.0.10`, and host runtime `26.18`.

**Confirmed: the version gap is real.** The pinned image ships
`intel-opencl-icd` and `libze-intel-gpu1` `26.14.37833.4-1~24.04~ppa1` against
this host's `26.18.38308.1-0`, matching the reporter's description.

**Confirmed: the reported multi-GPU failure does not reproduce here.** The
probe ran the exact call that failed for the reporter, on a host in the same
configuration class (`xe`, kernel `7.0.x`, host runtime `26.18`, same
Battlemage silicon `0xe223`, same `26.14` container):

| Arm | `ZE_AFFINITY_MASK` | Result |
| --- | --- | --- |
| A control | `0` | `device_count: 1`, exit 0 |
| B candidate | `0,1` | `device_count: 2`, both B70s enumerated, allocation on `xpu:0` and `xpu:1` succeeded, exit 0 |
| C trace | `0,1` | `urDeviceGet(... pNumDevices = 2) -> UR_RESULT_SUCCESS`, initialization proceeded past the reported failure point, no `UR_RESULT_ERROR_UNKNOWN`, exit 0 |

`torch 2.11.0+xpu` inside the container drove both cards without
`--privileged`.

**Therefore the simple version-gap explanation is refuted as stated.** A
`26.14` container on an `xe`/kernel-7.x/`26.18` host is not sufficient on its
own to break multi-GPU context creation, because that is exactly this host and
it works. The remaining candidate deltas against the reporter's environment are
narrower: kernel `7.0.0-28-generic` here versus `7.0.10` there, Ubuntu 24.04
versus Fedora 44 host stack, GuC firmware revision, and per-host P2P/BIOS
configuration.

**Confirmed: the recipe works on B70.** The full TP2 serve path completes.
Both workers initialize, weights load in 18.66 s at 14.13 GiB per card, KV
cache allocates at 13.89 GiB / 888,488 tokens, and the server answers
`/health` about 110 s after container start. Nothing in the reported failure
mode appeared at any point. This settles the functional half of the
submission: the recipe is real and runnable.

**Measured throughput on B70, consistent with the contributor's range.** 15
rows across 3 passes, repeated on two different card pairings:

| Metric | Median | Range | Stdev |
| --- | --- | --- | --- |
| Decode tok/s (excludes prefill) | **30.171** | 29.564 - 30.528 | 0.302 |
| Overall tok/s (includes prefill) | **29.427** | 24.201 - 30.287 | — |

The contributor reported 28.3 - 34.7 tok/s. **This lab's measurement falls
inside that range**, in its lower-middle. The recipe performs about as
submitted; the 27B FP8 TP2 configuration really does land near 30 tok/s on two
B70s, and there is no sign the contributor's figures were inflated or
cherry-picked from a different configuration.

The one figure not reproduced is the headline `34`, which the PR's ledger row
drew from the top of the contributor's own range rather than its middle. Peak
observed here across every row was 30.528 decode / 30.287 overall. The single
24.201 overall row is the first row of pass 1, carrying 2.126 s of residual
first-request cost; every subsequent row sits above 27.2.

**The measurements differ in dispersion more than in level.** The contributor's
table moves non-monotonically with prompt length (34.6, 34.7, 29.4, 28.3,
34.2). Across 15 rows here the decode rate is nearly flat regardless of prompt
length, with a standard deviation of 0.302 tok/s. The most likely reading is
that the contributor's spread is run-to-run noise on a small number of samples,
and that its high end was read as a headline. The underlying performance the
two of us measured agrees.

**Interconnect is not on the decode critical path.** The four B70s in this host
split across two root complexes: cards 0 (`0000:23:00.0`) and 1
(`0000:27:00.0`) hang off `0000:20`, cards 2 (`0000:43:00.0`) and 3
(`0000:47:00.0`) off `0000:40`. Running the same 15-row measurement on a
same-complex pair and a cross-complex pair:

| Pairing | Cards | Median decode tok/s | Range |
| --- | --- | --- | --- |
| Same root complex | 0 + 1 | 30.171 | 29.564 - 30.528 |
| Across root complexes | 0 + 2 | 30.482 | 29.752 - 30.964 |

The cross-complex pair measured 1.0% *faster*, which is inside the 0.302
standard deviation. There is no measurable penalty. Card selection was verified
from the host rather than assumed: under `ZE_AFFINITY_MASK=0,2` the two
allocations appeared on `0000:23:00.0` and `0000:43:00.0` at 1439 MiB each
while cards 1 and 3 stayed at idle 43 MiB.

This matches the arithmetic. At batch 1 this model moves about 1.31 MB per
token across the tensor-parallel link (`hidden_size` 5120, 64 layers), roughly
39 MB/s at 30 tok/s, against ~31.5 GB/s available on PCIe 4.0 x16 — about 0.1%
utilization. The link is latency-bound with tiny payloads, not
bandwidth-bound, so neither PCIe generation nor card placement explains the gap
to the contributor's figure. Note this conclusion is specific to single-session
decode; prefill-heavy, high-concurrency, or wider tensor-parallel
configurations were not tested and may behave differently.

**What this does not establish.** Sampling is enabled per the contributed
generation config (`temperature 0.7`), so outputs are not deterministic and no
exactness gate applies. This vLLM build did not populate
`prompt_tokens_details`, so `cached_tokens` reads `None` rather than a
confirmed zero; prefix caching is disabled server-side and every prompt was
unique, so cache-zero is inferred, not proven. Two of this host's four B70s
were used, matching the contributor's card count. Note separately that a 27B
FP8 model leaves too little room for KV cache on a single 32 GB B70 to reach
the advertised 256K context, so TP1 is not a workaround for this recipe.

Scripts, logs, and the result JSON are in [`validation/`](validation/).

## Known Issues

Recorded here rather than edited into the contributor's text.

1. **Hardcoded contributor path.** The prose requires the model at
   `~/.cache/huggingface/hub/models--Qwen--Qwen3.6-27B`, but the mount is
   `-v /home/dom/.cache/huggingface/...`. The command fails for every other
   user. Should be `${HOME}` or a documented variable.
2. **`--privileged` is broader than required.** `--device=/dev/dri` plus
   `--group-add` for the render group is normally sufficient for Level Zero.
   The probe in this directory deliberately runs without `--privileged`.
3. **Unauthenticated network exposure.** `--net=host` with `--host 0.0.0.0`,
   `--port 8001`, and `--restart unless-stopped` publishes an unauthenticated
   OpenAI-compatible endpoint on every interface, persisting across reboots.
   The health check uses `127.0.0.1`, which obscures this. Worth an explicit
   warning in the recipe.
4. **`--trust-remote-code`** executes model-repository Python. Combined with
   `--privileged` this compounds trust, and it is likely unnecessary for this
   model on a supported vLLM.
5. **Malformed benchmark table.** Lines 124-129 of the contributed README are
   raw tab-separated values outside any code fence and without a header
   separator; they render as a single run-on paragraph.
6. **Metric selection.** The measured range is 28.3-34.7 tok/s; the PR's
   ledger row promoted "34 Tokens a second", the top of the range rather than a
   median. The series is also non-monotonic in prompt length (2000-token prompt
   faster than 500), which usually indicates run-to-run noise or warm state and
   is unexplained. Sampling is enabled (`temperature 0.7`), so no exactness
   gate applies.
7. **No evidence label.** `CONTRIBUTING.md` requires every result to state its
   evidence level; the submission states "Working" and placed a performance
   claim directly into the promoted ledger.

Issues 1-5 are straightforward fixes. Issues 6-7 are why this entry is
`community-reported` rather than promoted.

## Open Questions For The Contributor

1. Host kernel version, GPU driver (`i915` or `xe`), and compute-runtime /
   level-zero versions on the 2026-07-22 test host. Now that the version-gap
   explanation is refuted and the recipe is known to work here, the exact
   kernel and distro identity of all three hosts is the only thing left that
   separates a working deploy from a failing one.
2. Benchmark methodology behind 28.3-34.7 tok/s: how many repeats, what metric
   definition, cold or warm, and whether prefill was included. The level agrees
   with this lab; only the spread does not, and knowing the method would settle
   whether the 6 tok/s swing was sampling noise.
3. Any logs or JSON from the original run.

## Disposition

Promoted from `community-reported` to **`B70-tested`** on 2026-07-25. The
recipe was executed in the reference lab and works: it serves `Qwen/Qwen3.6-27B`
at native FP8 across two B70s at roughly 30 tok/s, which is the substance of
the contribution and is now independently established rather than taken on
report.

This is a good contribution. The recipe is accurate, the configuration is
sound, and the performance the contributor described is broadly what this lab
sees — 30.171 tok/s median decode sits inside their stated 28.3 - 34.7 range.

It stays at `B70-tested` rather than `B70-verified` for two reasons, neither of
which is a criticism of the submission. First, `B70-verified` requires a
quality gate, and this configuration runs with sampling enabled
(`temperature 0.7`) so no exactness check applies. Second, the specific number
carried into the ledger row was `34`, the top of the contributor's range, and
the lab measures the middle of it.

Recommended handling: cite **30.171 tok/s median decode** as the B70 figure
when this recipe is referenced, rather than 34, and treat the contributor's
range as corroborated at its lower-middle. The entry stays in `community/`
because it is a contributed deployment recipe rather than an optimization
result, not because the evidence is in doubt.

The recipe is genuinely useful: it is the working path to a 256K-context FP8
Qwen3.6-27B endpoint on two B70s, and the flag and environment matrices are
reusable. The known issues below are worth fixing before anyone follows it
verbatim, but they are ordinary rough edges, not defects in the result.
