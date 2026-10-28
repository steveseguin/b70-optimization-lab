# Long-context exact select intake — 2026-10-28

Candidate only, default off: `OWNRT_SELECT_LONG=1` additionally requires existing TOPK/FAST switches. Patch changes only select_fast.hpp and specialised_submit.cpp. Canonical sources remain untouched. Uses CM16/32/64 cached integer radix selection selected by admitted extent; same sorting/ties/score arithmetic, same capacity scratch stride, device refuses cache overflow. Existing CM16 default entry point preserved.

B70 card43 standalone kernel gate: exit 0, 0 failures over 36 cases × 2 candidates, checking every score bit and selected ID against canonical TOPK. Includes T1/T2/T32, 65K/121K/131K/200K/262K seam cases, many ties and mostly-zero keys. Does not establish model-state parity, error-path completeness, or production dispatcher integration. T32 timing invocation skips this already-passed exact gate; its printed exactness line is inherited harness wording, NOT another gate.

30 timed repetitions; profiler GPU median Stage1 microseconds (T32):

| Position | Canonical | Auto cache | Auto capacity |
|---|---:|---:|---:|
|121852|96.25|30.00|32|
|200000|146.67|114.90|64|
|262112|221.04|140.21|64|

Hot measurements. Cold Stage1 respectively100.42→30.31,146.67→114.06,220.21→142.40us. ForcedCM64 at121852 is89.17us, so selecting capacity from actual extent matters. T1 Stage1 at12185294.38→29.06us and262143185.52→84.58us. Stage0 benchmark reference is older than production: NONE of the reported Stage0 gain is a new candidate gain. No end-to-end target speedup claimed; likely small lever, close after one integration state gate rather than extensive further microbenchmarks.

Both isolated units completed normally, no retries, no new passive fault delta, no remaining GPU holders. Actual existing PP4 planner floors read before requests: start RAM100000000000, root27000000000, evidence2147483648 bytes. Observed RAM~102GB and root27.88GB met these. No power/memory/server changes; only card43 opened. Units ownrt-select-long-c43-20261028 / ownrt-select-long-t32-c43-20261028. Flags/toolchain are recoverable in parent transcript; standalone source and logs preserved here. Compile with oneAPI2026.0 icpx strict fp flags matching existing select harness, overlay header from candidate; no full-engine build performed.

Next: shared full build after root finishes main.cpp/rank.hpp, single existing persistent-service full-state comparison with LONGoff/on at context262144 and real long prompt; then fair same-service prefill timing only if profiling shows material share. Do not repeat model loads for this small kernel lever.

## Cost ceiling disposition
Actual run launch-plan.json lists QSAselect sites2+3+3+4=12. prefill_engine.hpp:179 computes32rowgroups at context262144, :316 issues one selectgroup per32rows. For actual121852prefillrows, 476chunks of256 plus finalpartial yields12×ceil(121852/32)=45696Stage1calls. Multiplying every call by endpoint observed66.25us gain gives3.027s (0.45% of671.965s target); eliminating entire observed endpoint96.25us gives4.398s(0.65%). These are generous endpoint extrapolations, not mathematical runtime bounds; no claim that early positions share endpointtime. Max context prefix262142 would98304calls and7.946s endpointdelta at80.83us. Integration deprioritized; preserve optionalpatch only.
