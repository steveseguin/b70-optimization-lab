# Ornith 1.5 35B-A3B: beta/GDN fusion interaction on the nine-feature stack

Date: 2026-08-23 EDT

Status: **CLOSED SERVER-NEUTRAL — do not ship**

Ornith's Qwen-derived recurrent graph has a 32-value beta sigmoid immediately
before each Gated Delta Net operation. An earlier exact fusion of that sigmoid
into GDN was neutral on the then-current stack. It was retested because the
newly accepted GDN RMSNorm/SiLU-gate fusion changes the downstream scheduling
boundary and the two paths can coexist: beta/GDN executes early, while the
RMSNorm/gate matcher still fires after the parallel `z` projection becomes
ready.

The same-binary correctness gate passed. Door-off and door-on 128-token
transcripts both hashed to
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
The candidate recorded exactly 3,810 beta/GDN hits and 3,810 downstream
RMSNorm/gate hits, proving that both boundaries executed across all 30
recurrent layers. Together they replace three stock launches with one per
layer, but beta/GDN contributes only 30 newly removed launches/token beyond
the accepted parent.

The mirrored engine screen was repeatably positive:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `119.666769`, `121.158678` | **120.412724** |
| candidate | `122.123470`, `121.741812` | **121.932641** |

That is +1.2623%, with both candidates above both controls. It did not survive
the required fresh-server A/B/B/A gate:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `117.480886`, `117.779699` | **117.630293** |
| candidate | `117.331443`, `117.814285` | **117.572864** |

The serving delta is -0.0488%. All 48 responses were fresh, every request had
`cached_tokens=0`, every prompt was unique and run once, and every final gate
passed. This is a valid endpoint-neutral result, not a failed mechanism or an
invalid benchmark.

The complete candidate source is preserved at
`../patches/llamacpp-ornith15-beta-gdn-nine-stack-server-neutral-20260823.patch`.
Raw engine/server records and structured evidence are under
`../data/2026-08-23-ornith35b-beta-gdn-nine-stack-*`. The build and source were
restored byte-for-byte to the accepted nine-feature identities after testing.
