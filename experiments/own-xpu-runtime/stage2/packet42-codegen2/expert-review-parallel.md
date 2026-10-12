# Independent arithmetic review of parallel candidates

Read parallel.hpp, parallel_submit.cpp, parallel_gdn.inc, parallel_cpu.cpp, parallel_native.cpp and the unchanged packet29 specialised/round2 cores. This reviewer authored the separate expert family, not these candidates. No device program ran.

Dense: each of the four partials retains the same 32 lanes, eight-element lane tiles, increasing tile sequence, adjacent lane reduction tree, and ((p0+p1)+(p2+p3)) FP32 finish before BF16. K6144 split boundaries are aligned to 256, as required by the segment helper. The candidate deliberately serializes four partial calculations into four independent accumulators in one subgroup per row; it does not retain four subgroups per row. This removes the finish launch but decreases subgroup-level parallelism, and is a timing candidate only.

Route: the original rounded FP32 division ex[k]/den is still performed before comparisons. Integer rank counts partition comparisons without changing the stable larger-value/earlier-index tie rule. The 32-lane unsigned reduction cannot overflow at N512. The maximum, exp and sum preparation and final selected normalization retain the old arithmetic and odd-tail upper-tree helper. Route NaN rejection remains in stage0. Stage count drops five to four without a serial 512-comparison lane.

GDN: specialization is token1 only and rejected otherwise. Flags are host-specialized to the admitted even variants. The q/k four-elements-per-lane loops, tree32 reductions, q normalization divisions, decay, prediction, delta, output and BF16 state stores remain in the old order. The removed terminal subgroup barrier has no subsequent state reader in this token1 kernel; the completion event orders later kernels. The permitted input/output state alias touches the same group's non-overlapping state range.

Required fixes sent to the implementation agent: preserve incumbent live/device/alignment and binding-alias checks in the new submit wrapper; directly gate rank_lane<512> rather than only duplicated host loops; correct the odd-rank test comment (the initial data only used j%7, not the claimed signed-zero/Inf/NaN patterns). The checked fixture suites already cover route NaN rejection, invalid position, inactive/blocked control state, ties, token counts1/3 for routing, and three GDN storage fixtures in two compilers/two fresh processes. Independent fixture bytes match incumbent and frozen CPU reference in the qualified scope.

Recheck: live/device/alignment/alias validation is restored, including the existing state5/state7 alias exception and forbidden scratch/control aliasing. The CPU gate now invokes rank_lane<512> directly with four denominators, equal values, signed-zero ties, varied finite inputs and separately labelled nonfinite diagnostics; the inaccurate odd-length comment is corrected. No blocking arithmetic or binding-contract finding remains in the reviewed code. The one-subgroup-per-row dense scheduling trade remains an explicit candidate scope limitation.

- `parallel.hpp` SHA-256 `94e13105298711f01cb283a284806297e93f0f69302447c212392804bd85478a`
- `parallel_submit.cpp` SHA-256 `8c7c25aa8451003f0a18bdb0930fb720d79d503c2af7ffa0e0ad213a49f1986b`
- `parallel_gdn.inc` SHA-256 `695c96a963151ae947892e7134edffde2c6149437f1451c19c27989191c8a07b`
- `parallel_cpu.cpp` SHA-256 `a2eaf69eb8969f6675b6c249b31bfbee73a512e3808ee6e42db381060e091c83`
- `parallel_native.cpp` SHA-256 `0ef018254510bab79010f951efd15ce00b120c8fdb4f21e383fa9ae747010078`

Final metadata recheck: restored `route_gather` label keeps the diagnostic ng route distinct from the production `route` family. Arithmetic/API files unchanged.

- Final `parallel_native.cpp` SHA256 `1b662a3462877c577f23dba36ca7de3df8ff946ea83d532c75b1b2409a5da7e4`
