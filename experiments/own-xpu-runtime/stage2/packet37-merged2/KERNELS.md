# Packet37 kernel registry

This packet merges existing exact arithmetic and host scheduling changes.
It contains no packet37 card measurements and claims no speed.

| New dispatch name | Scope | Arithmetic retained |
| --- | --- | --- |
| `p33.down.select` | Routed IQ4_NL expert down, K640 | Selected-byte decode, original lane and tree order |
| `p33.down.bank` | Routed IQ4_NL expert down, K640 | Bank-byte decode, original lane and tree order |
| `p33.gate.restrict` | Paired IQ2_S/IQ3_S expert gate/up, K2560 | Packet28 exact paired arithmetic |
| `p33.dense.segment` | Every dense class below | Expanded/scalar decode, lane tree, split finish |
| `p33.qsa.shape` | QSA attention score/softmax/value | Existing round2 body with validated shape constants |

`p33.route.rank4` is deliberately absent from the admitted dispatch registry.
Packet25, packet27, packet28 and packet29 vocabulary remains available.

The dense class list is `gdn.qkv`, `gdn.z`, `qsa.qgate`, `qsa.k`, `qsa.v`,
`qsa.iq`, `qsa.ik`, `attention`, `logits`, `ple.key`, `ple.value`,
`hc.a.gate`, `hc.a.low`, `hc.a.inject`, `hc.f.gate`, `hc.f.low`,
`hc.f.inject`, `router`, `shexpgate`, `shexpup`, `shexpdown`,
`final.gate`, `final.low`, `gdn.a`, `gdn.b`, and `shared_gate`.
`hc.gate` and `hc.low` remain supported dispatch aliases.

Compile-time K families are 320, 640, 2560, 6144 and 10240. Q8, F32 and BF16
have all five. Q6 has 2560, 6144 and 10240; K320 and K640 cannot encode a
whole Q6 block. Q6/Q8 use the existing expanded byte-code and FP32-scale
layout. F32/BF16 use their unchanged scalar layout. Both split1 and split4
are compiled: quantized variants 6/7, scalar variants 0/4. The runtime keeps
each class's original variant; choosing a candidate does not choose new
arithmetic. The CPU Cartesian gate covers every class at all valid formats
and both splits, including odd tails, unaligned ranges and empty ranges.
K1/K2 use the 34 concrete model shape/format workloads in `p28/registry.hpp`.
K1 also runs the separate `p33-linked-fixtures` owner: 216 byte comparisons
exercise all 36 compiled dense type/K/split instantiations, including split4
finishing, across six input modes. This closes template coverage beyond the
checkpoint’s concrete class/format combinations.

Dense identity checks compare against the reference expanded core with both
host compilers and two fresh processes each. Lane sums, trees, full rows and
BF16 results are compared in bits. The inherited nonfinite policy remains:
no NaN tolerance is used; exceptional diagnostics record exact mismatches but
are not qualified as a supported production domain. See
`p33-candidate-gates.json` and `review-dense-independent.md` for current CPU
evidence. Linked device lowering still requires the two fresh K1 owners.

K2 retimes the exact packet29 choices recorded in `dispatch-incumbent.json`.
That file is provenance, not a packet37 measurement. The controls are also
compiled into `k2_incumbents.hpp`. R5 remains a timed alternative whenever
it differs from the control. Every registered candidate has 200 repetitions;
payloads above 8,000,000 bytes use eight full-size rotating payloads and
separate reread diagnostics. Candidate comparisons require on-card exact
bytes and complete repetitions. The individual candidate admission threshold
remains strictly below 90% of its same-run incumbent cost, for every workload.

The three small fusions are measured separately against their R5 member
sequences, then compared with the sum of the members actually selected by
this K2 run. Both HC sites and every FFN format must favor fusion. Ties keep
members; aliases do not count as extra operations. Missing or invalid timing
fails closed. This fusion comparison uses the cheaper complete choice rather
than requiring an additional 10% gap. The final dispatch is written as
`dispatch-measured.json`, `dispatch-rank0.json`, and `dispatch-rank1.json`.
The rank files intentionally carry the same policy from the one-card K2;
they are not separate per-card speed measurements. Coordinator overrides
remain explicit, validated, hash-bound diagnostic choices.

The fixed `p33.qsa.shape` body requires capacity 128, budget 2048 and one
token. Prepared W windows use capacity 256 and therefore execute its generic
round2-body fallback. K2's fixed-128 QSA result cannot establish a QSA gain
at capacity 256; measure the complete W run independently. No new 256-shape
specialization or arithmetic is introduced here.
