# Packet109 do not repeat

| Arm | Finding | Evidence / revisit condition |
| --- | --- | --- |
| Fully inline down/mixture/blend expression | GNU changed a final NaN payload despite identical finite arithmetic | `evidence/rejected-v1/`; preserve operand boundary and exact bytes |
| Materialized final operands in both compilers | GNU passed; Intel changed its production NaN payload | `evidence/rejected-v2/`; keep Intel's original expression |
| Reuse O2 byte verdict for GNU O3/native | Materialized and fully inline forms differ under final flags | `evidence/rejected-v3-native-GNU-flags/`, `evidence/rejected-v4-native-GNU-inline/` |
| Specialize the production reference inside the fixture | Call-site optimization changes NaN payload behavior | Final `production_cpu.cpp` compiles actual NgHost separately with runtime shapes; GNU host retains its complete blend loop |
| Shared generic fusion interpreter | Prior packets found severe device cost | `CENSUS.md` prior-attempt table; this packet has two fixed shapes |
| Early return from fused execute_site | Would bypass common BF16-writer invalidation | Final implementation uses the normal common tail |
| Omit audit serializer for inherited p60 object | Full-shape capture cannot hash its prepared state | Replace the hashed-filename p60 object in the CPU audit link; retain first failure log |

CPU evidence is not device model quality or a speed result. The lane B bracket
is pending. Close the candidate only after its actual engine result, and retain
the exact failure or successful result rather than inferring it from launches.
