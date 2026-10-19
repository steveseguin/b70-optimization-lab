# Chain 176-a: ran the PARENT poll/copy line, not the packet176 candidate (generator flag-wiring bug); not submitted

`packet58-onecard-176-a` ran 12:01–12:36 UTC on card 0, whole host, quiet. Every window passed and was exact: KD, W2m, WS 12/12, WS128x 12/12, WS128 12/12. The GPU fault count stayed 2.

| Window | Class-balanced tok/s |
| --- | ---: |
| WS128x | 32.179 |
| WS128 | **31.832** |

**This is not a measurement of the packet176 candidate.**
- The run records show `"foreground_io":"copy"` 2,386 times and no wait-policy field.
- The generated `suite_driver.py` defines `native_command` twice. The generator's wrapper, which appends `GENERATED_CHAIN_FLAGS = [('--wait-policy','spin'),('--foreground-io','kernel')]`, sits at line 214–218, *after* the module's `__main__` entry. Run as a script, `main()` executes with the original `native_command`, and the flags are never passed.
- `onecard_chain_derive.py --predevice-check` imports the module (so the wrapper exists at check time), and so passed.
- 31.83 tok/s matches the old poll line (packet58aj, 31.84 warm controls). That is consistent with neither spin nor kernel I/O being active.

**Not submitted:** WS128 is below the 34.573038 threshold, and it measured the wrong configuration.

The packet176 bracket result stands as measured:
- B0/B1 35.982/35.981 vs warm controls 34.621/34.640, +3.87%, 60/60 exact;
- slow-readback fraction 0.40 → 0.0.

It still needs a correctly wired chain.

**Fix (resume queue):**
- The generator must insert the flags inside `native_command` (or before the `__main__` guard).
- `--predevice-check` must execute each window **as a script** (`python3 -B suite_driver.py …` with an argv capture) and assert that the native argv contains every chain flag.
- Every chain window must record the effective `wait_policy` / `foreground_io` and refuse if they differ from READY's `chain_flags`.

The owner paused the campaign at 12:02 UTC; no rerun until the pause lifts.
