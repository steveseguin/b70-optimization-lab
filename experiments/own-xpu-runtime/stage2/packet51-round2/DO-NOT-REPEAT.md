# Packet 51 negative and qualification index

See the evidence-linked [CPU preparation closeout](PREPARATION-CLOSEOUT.md).
No row below is a GPU performance verdict.

| Arm or mistake | Outcome | Revisit condition |
|---|---|---|
| Call production `finish` with a `Launch` and no boolean | CPU compile refusal; route requires `finish(..., false)` | Follow the actual engine interface and compile the matched adapter |
| Depend on enclosing translation-unit adapter includes; name a generic helper `equal` | Standalone compile exposed missing types and ADL into `std::equal`; explicit dependency and `byte_equal` correct the build | Keep the standalone compile gate |
| Run Intel direct test without compiler-library runtime path | `libiomp5.so` loading refused before arithmetic; compiler-lib rpath corrects loading | Verify the process reaches its arithmetic receipt, not merely compilation |
| Treat direct IQ2 nonfinite decoding as byte-identical after GNU checks | Intel failed check 276870: half 0x7e01, nibble 0, index/signs 155; rejected source and receipt retained under `evidence-cpu/nonfinite-rejected/` | Fallback now passes per-compiler exact checks; all admitted phases agree across compilers, while the inherited NaN payload diagnostic differs. Packet48 still rejects every nonfinite model scale before repacking |
| Substitute one-workgroup HC inject under the existing matched control | Not adopted because scratch writes and physical launch count differ | Separate registration with full mutable-state and launch accounting; no measured speed verdict exists |

Final qualification is recorded by source-bound gate receipts and the seal.
Neither a corrected compile nor an unadmitted-input label upgrades a failed
arithmetic arm into an accepted kernel.

- Do not reject the production route's explicit error/active inputs for aliasing
  their identical tail controls. Keep the original route42 ABI checks and test
  the actual Engine composition. The first full-layer CPU run refused safely;
  [receipt](evidence-cpu/production-alias-refusal/receipt.json).
