# Packet168 measurement status

**No device run has occurred. No measured ranking or priced top two exists.**

The device report (`evidence/device-census-*/CENSUS.md`) will list these rows:

| Row | Kind |
|---|---|
| attention | measured class (isolated body probe, exact repair) |
| gdn | measured class |
| routed_experts | measured class |
| router_shared_expert | measured class (one fused class) |
| dense_hc | measured class |
| norms_glue | measured class |
| residual | control ms/token − Σ measured; includes cross-card transfer, split head and overlap; **not causally isolated** |

Packet110, packet128b and assumed transfer fractions are never substituted for
missing measurements. Arms are diagnostic and never reported as speed.
