# Qwen3.8 Flash-Next grouped serving stage A4 qualification preregistration

Date: 2026-08-31
Status: frozen after A3 schema-contract negative, before tensor work

A4 is the exact recovery successor for the already assembled A2 serving stage.
It retains A3's explicit successful return from the no-render-owner guard and
all original A2 package, source, loader, focused-test, GDN, MoE, XCCL, journal,
output-hash, and interpretation gates. It performs no server launch, full model
load, throughput measurement, reboot, or full-load marker write.

The only substantive correction is the package schema relationship. The
accepted native extension has 32 `_xpu_C::` schemas and does not link or map
the grouped library. The pinned candidate has 46 schemas: every one of the 32
accepted schema strings is unchanged, none is removed, and exactly 14 known
schemas from the pinned kernel chain are added. The candidate must map its own
grouped library and expose the exact
`cutlass_grouped_gemm_interface` schema. Both stages must map their own GDN
library and the exact SYCL runtime, and both must retain the 23-argument GDN
ABI. Any removed schema, unexpected addition, wrong mapping, or ABI change
fails closed.

Frozen identities:

- original A2 qualifier:
  `870529a3e9c37599f77f38460795a2651e9a3ff4701c1a46d7dac73f8b8152a2`;
- A4 inspector:
  `60f0264f9971d699b8cac39afe9c55dba0d4b3566cc9b793e5465c3e3ebeefc2`;
- imported A2 inspector dependency:
  `b37a2e15d61826d1deca3b3dab03028e18b6e7f1a77776bd52b09a6d6d6d40d4`;
- A4 inspector CPU tests:
  `88e8b51a49e17909405fd6ee6a23ee9d0dfba4a43815f775f7b82f07495a089b`;
- derived A4 qualifier:
  `894cc6b276647051d6dd34057d3a8158f97a0600a9261e990901c4e01845a3ae`;
- A4 wrapper:
  `cc78c3ec2d26fc565f2eb877b8d0f42090b3a1df346226d599cf56a7b11340fa`;
- evidence directory:
  `grouped-serving-stage-eeee7d6-a2-qualification-a4`.

Before execution, formatting/static checks and all four CPU contract tests
must pass. Separate clean-process imports of the exact accepted and candidate
packages must reproduce the 32-preserved/14-added/zero-removed relationship.
An independent review must find no blocker. A complete A4 pass authorizes only
freezing the separate A30 endpoint candidate; protected MTP0/MTP4 results stay
unchanged.
