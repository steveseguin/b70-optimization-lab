# Packet33 closeout — generated code, CPU only

Question: can the exact shipped SPIR-V and offline B70 GEN explain surprising
candidate timings and support more deliberate exact candidates?

Identity: packet29 recorded device objects/link flags,24 byte-identical embedded
SPIR-V images, target PCI0xe223 revision0, ocloc26.18, precise divide/sqrt API
options. [modules](modules.json), [options](runtime-options.md),
[build receipt](build-receipt.json). No device discovery, device binary execution,
power/memory/swap setting or external packet modification occurred.

Outcome: offline dumps work. SIMD32 is a real dispatch; qword address math often
uses SIMD16 instruction halves. Some old expert candidates spill heavily.
Paired gate removes duplicate decode/address work. The final down.bank source
iteration has7 rather than15 data messages per octet and188 rather than169
instructions against p29.wg32. It is a mechanism result, not a measured win.
The predictive model failed held-out validation and is not qualified.

Retained: complete extracted static census; independent finite-path expert-down
reviews; pinned measured input rows; failed model and ablation; initial/final
candidate source patch and CPU receipts; exact candidates; compiled, unrun K0
and timing harness; negative select diagnostic. Raw assembly remains ignored
under build; only extracted tables and short excerpts are committed.

Failures/uncertainty: offline JIT option equivalence lacks an actual runtime
trace; not every kernel has a proved dynamic per-weight count; generic
activation gives no measured launch floor; finite host identity does not
qualify exceptional inputs or device-only vector execution. Existing source
nonfinite and historical QSA fixture discrepancies remain visible. See README.

Next boundary: coordinator runs documented K0 then K2, separately authorized.
No prediction or offline success should enter a runtime dispatch until measured
byte equality and the normal quality/repeat gates pass. Revisit the model with
matched dynamic path and memory/occupancy features if a useful predictor is
still needed. This closeout ends the CPU packet, not the optimization lane.
