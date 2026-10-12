# Independent complementary tiny-kernel review

Reviewed source read-only, independently of the author; no device binary ran.
The reviewer authored expert/production-route candidates, not this family.

No blocking arithmetic-identity finding remains in the reviewed source.
Norm and combine-norm reuse the incumbent specialised body and its exact
stages/trees. Select reuses round2 group arithmetic and its existing local
memory/barriers; only team width changes. Its extra capacity-256 fixture
retains the existing fixture values and exercises the larger mapping.
Streams, combines, ple.add, begin, commit and status checks reproduce the
adapter equations, rounding and control guards. Status uses the same adjacent
FP32 sum of 0/1 flags including the odd tail, not a changed boolean reduction.
Begin retains its distinct handling of a preexisting error; commit remains
active/error gated. Flat input/output/control aliases and logical extents are
validated before device submission. Capture guards stay <=1024 bytes.

CPU fixture gates cover incumbent/reference byte equality under both host
compilers and fresh processes. Native timing submits the runtime incumbent,
checks bytes before and after timing, alternates arm order, and retains 200
GPU event and host wall samples for each timing-eligible case. Diagnostic-only
fixtures remain visible but cannot enter dispatch. Buffer payloads are below
8 MiB. Failures are recorded as rows; infrastructure errors are separate.

The updated summary normalization correctly expands comma-separated runtime
class aliases, requires both 200-sample GPU/host arms, marks untimed fixture
rows diagnostic, and prevents any failed candidate from entering dispatch.
A sampled geometry still needs coordinator evidence and the registered
integration guards; this review supplies neither a speed verdict nor device
identity evidence.

- `extras_core.hpp` SHA256 `1891cd081e315a39f91058c903d6df408955ad5e07848cc079284f1ea937be51`
- `extras_native.hpp` SHA256 `660a1173fa4f1dc205635b6dc4c759dcf9d8a28aad7db76c58cf0456da618303`
- `extras_cpu.cpp` SHA256 `b36a76cc8772558ace18d47a07e02eafed1cd6b599b3fbbec5fa9f3b9b776d1a`
- `extras_timing.cpp` SHA256 `45e7fdf11093017fb2c97f1630119a2f912db6d7bbec3a43e0f85e113c3633cb`
- `summarize.py` SHA256 `9a26fb3812f656807bd06affa25f7e8f6556a17c295c59fab27444ec5940c038`

Final metadata-only recheck: extra flags/heads/capacity/budget row fields do not change arithmetic or timing.
- Final `extras_core.hpp` SHA256 `1891cd081e315a39f91058c903d6df408955ad5e07848cc079284f1ea937be51`
- Final `extras_native.hpp` SHA256 `660a1173fa4f1dc205635b6dc4c759dcf9d8a28aad7db76c58cf0456da618303`
- Final `extras_cpu.cpp` SHA256 `b36a76cc8772558ace18d47a07e02eafed1cd6b599b3fbbec5fa9f3b9b776d1a`
- Final `extras_timing.cpp` SHA256 `bb865b514e25a03bd6c7fb845c9d15a8dcd7cc09b0a6c89023d54ddd707dc084`

Dispatch scope recheck: norm aliases hc.a.norm/hc.f.norm/final.norm use the
same four-stream shape in packet3/step/plan.hpp (hc() line106 and final call
line291). Combine-norm now uses only combine_norm.diagnostic and is not timed
or mapped to runtime classes. These metadata changes preserve the arithmetic
review.

- Scope-final `extras_timing.cpp` SHA256 `5cfe8635189fed3d71f7b7cbfa2f7a5ed3292e73e110e7a0ccd66040ae9dc0bd`

## Final scheduled ABI and in-place review

Independent re-read compared the candidate with packet3/step/plan.hpp and
packet29 adapter.cpp. The scheduled slot mapper now preserves the actual
orders: check [status,error,active] -> error; commit [error,active,position] ->
position; begin [active,position] -> error. Other leaf classes append active
and error after payload inputs. The signature-specific native guard verifies
these scalar outputs and inputs alias the same tail controls. Compact ABI
remains available for host fixtures. Compact.in remains bounded to at most
three payload views; the scheduled slot map does not expand that array.

hc_combine and ple.add now permit output=input0 only with equal extent/type,
and continue rejecting other writable aliases. The original operations read
and write the same element of input0 and preserve every rounding point.
Native timing submits the actual scheduled ABI to both the runtime incumbent
and candidate and uses input0/output aliasing for these two graph operations.
Upload skips the duplicate output allocation to avoid clobbering the input.
Each repetition restores the input and controls before either arm.

CPU gates compare compact and scheduled ABI against both integrated Core and
an exact extracted incumbent, including in-place cases, odd sizes, inactive,
sticky errors and nonfinite values. Alias equality explicitly checks mutated
input0 as well as output/control state; no alias result is silently ignored.
The scalar candidate binding map feeds the same tail control addresses as the
incumbent. No blocking arithmetic, scheduled ABI or alias issue was found in
the final reviewed source. Fresh compiler gate receipts remain the build
agent's evidence; no device binary was run by this review.

- ABI-final `extras_core.hpp` SHA256 `041f30fe4249ae0fd1b635633fbf1bcff5e4110e77169f09e5880038899450ef`
- ABI-final `extras_native.hpp` SHA256 `4aec334590e1c8473f76f1096f4bc244375cfee36b0bbc0487269497fe153007`
- ABI-final `extras_cpu.cpp` SHA256 `fabd59274115d0fa39afe81f33c94cc9f09d6006c3d900cbaea3a5eb53ce1c53`
- ABI-final `extras_timing.cpp` SHA256 `6c442c4045fc4fe9cde7420620db7fb71d631aff3c08471cf1fe879887402363`
- ABI-final `extras_incumbent.hpp` SHA256 `8286959f802180c26e29f106d06dd85fc9694ba5a03c9f42eacb5baa8723aca8`
