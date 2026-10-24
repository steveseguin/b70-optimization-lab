# Combined attention and Q6 QKV candidate preparation

This additive entry starts from the frozen attention candidate. It adds only
the 22 graph-selected Q6_K GDN QKV projections, each N10240/K2560, using the
unchanged p33 variant6/split1 operator. The original 48 attention choices remain.
The other QKV formats, Z, experts, controls, full head, MTP and all arithmetic
headers remain unchanged. Both candidate flags and `--gsq-packed` are required.

`prepare.py` checks the frozen attention source and original per-translation-unit
dependencies. Only the main entry changes. The other 39 original objects remain
byte-identical; no shared inline types, decoder or Matrix declarations change.
`overlay.patch` is the exact additional delta. The generated policy is compiled
against small synthetic metadata structs to test the real selectors and
admission errors without constructing an Engine or Device.

The existing Q6 CPU proof covers all binary16 scales, signed scale bytes and Q6
codes, plus complete synthetic rows. The three fixed actual native micro cases
passed every saved BF16 output comparison. These are prerequisites, not a claim
that the combined full model has passed. All twelve original prompts still need
target-only and MTP exact token and full target-state gates against the frozen
baseline before promotion. Separate-session timings are provisional.

No additional scan of all 22 tensors is required for preparation: target loader
header/descriptor admission stays unchanged, and the scale proof includes the
exceptional encodings. Only three actual weight payloads have been hashed in
the Q6 micro preparation. No all-22 finite-scale claim is made.

The extra expansion relative to the attention candidate is 288,358,400 bytes:
183,500,800 on rank0 and 104,857,600 on rank1 for split24. Combined device
forecasts are 30,947,490,698 and 29,824,495,508 bytes. The initial host admission
forecast increases by 288,358,400 bytes as well; this is a conservative admission
increment, not a measured resident-host allocation. Actual allocation census
must still agree during qualification.

From this directory, preparation and read-only native recipe inspection are:

```sh
python3 -B prepare.py
python3 -B build.py --mode native --plan
```

Preparation requires a fresh generated destination. Builds retain each attempt
and use the existing compile coordinator, nice19, helper cores, two threads,
4GiB address-space limit and root floor plus250MiB reservation. Root reviews
the native recipe before the sole native compile. The native binary is never
invoked by the build helper.
