# Packet45 HC activation repair, 2026-10-13

## Question and identity

Why does the sealed packet45 K1a stop at `case=54 version=0 buffer=5` on both
card pairs? The original runtime was sealed at `7b0ec5bb5`. Device failure
inputs are hashed in [protected-inputs.json](evidence/hc-activation-fix/protected-inputs.json).
Exact copies of the nine coordinator failure files are retained in
[the verified failure archive](evidence/hc-activation-fix/original-device-failures-retention.json).
The coordinator owns recovery and the existing fault latch. This repair is CPU
only; it does not establish a device pass or a speed result.

## Root cause

The exact fixture constructors produce **55 cases**: the HC cases are 51–54.
Case **53**, scenario 2, seeds error word 7. Case **54**, scenario 3, puts BF16
NaN `0x7fc1` into the first activation input. Buffer 5 is the activation output.
The new gate calls the shared, unmodified constructors rather than relying on
manual counting. Its JSON records this mapping and versions 0, 1 and 9.
The prefix count is `4 + 2 + 2 + 3 + 15 + 21 + 2 + 1 + 1 = 51`.

| Case | HC scenario | Input/control |
|---|---|---|
| 51 | 0 | ordinary finite input |
| 52 | 1 | active word 0 |
| 53 | 2 | sticky error word 7 |
| 54 | 3 | first input `0x7fc1` |


The expression `x * (1 / (1 + exp(-x)))` has two different NaN operands for
this input. Our deterministic `exp` returns canonical NaN `0x7fc00000`, while
`x` retains payload `0x7fc10000`. Ordinary floating multiplication does not bind
which NaN payload is returned across host and device code generation. CPU
compiler/optimization changes reproduce the ambiguity. The exact-output check
correctly refuses differing bytes. This is not an error-buffer propagation
failure: the pre-seeded case passes unchanged, including exact error word 7.

Packet44 does **not** contain these four HC adapter scenarios. Packet45's tiny
activation integration added them. The version-0 `ng::group` and device entry
were unchanged from packet44, so this exposed an existing unspecified payload
choice rather than a new rank-placement or control-buffer regression.

## Why the old CPU gates passed

The full original GNU fixture was rerun without a device and passed all 55
adapter cases, with 3,427 aggregate adapter checks; its retained receipt is in
[original-full-fixture-retention.json](evidence/hc-activation-fix/original-full-fixture-retention.json).
The old arithmetic checks compared functions compiled together under the same
host settings. Agreement there did not guarantee payload stability under the
device compilation. The 79 mini cases and six model cases did not inject this
nonfinite HC input. `fixture_validation::only` deliberately skips computation
and output comparisons; it validates bindings, not arithmetic.

## Change and retained evidence

`detmath::silu_div4` now tests the input bits before floating arithmetic. For
any NaN, it preserves the sign and payload and sets the quiet bit. For finite
inputs, the equation and rounding order remain unchanged. The serial core,
version-0/version-1 fallback, p42 range implementation and p39 fused epilogue
all call it. No tolerance, fixture exception, error reset or finite-output
change was introduced. Diagnostic NaN payload behavior is now explicit.

The fixture construction was extracted into a shared function without changing
its cases. General mismatch messages now include the first differing byte and
its actual/expected values. The seal requires the new CPU gate and checks its
source, executable and raw-log hashes, case identities and compiler matrix.

[Before](evidence/hc-activation-fix/before.json): five of six compiler arms fail,
759 checks in each failing arm. [After](evidence/hc-activation-fix/after.json):
all **4,752 checks** pass (792 per arm). GNU and Intel each use O0, O2 and
O3/native. Every arm includes the four actual HC fixture scenarios and all
254 signed BF16 NaN encodings across the baseline, p42 and fused functions.
The pre-seeded error case passes before and after, including version 0.
The [retained GNU fixture byte comparison](evidence/hc-activation-fix/fixture-byte-diff.json)
compares two 23,393,176-byte outputs. Only 35 bytes change: three direct NaN
payload bytes (`c0` to `c1`, once per activation implementation) and one 32-byte
output digest. The first changed byte is offset 6,712,864, exactly where the
retained failed device output stops before writing case 54's output buffer.
This explicitly records the diagnostic NaN byte refinement; the pre-seeded
error scenario is unchanged.
The source hashes are checked throughout each arm. These are CPU proofs;
actual post-fix device comparison remains the coordinator's gate.

## Qualification and handoff

All four build modes were rebuilt, and the original CPU suite passed again.
The new seal binds **24 gate receipts and 41 build artifacts**. The detached
no-launch admission binding also passed. See
[qualification-summary.json](evidence/hc-activation-fix/qualification-summary.json)
and [BINARY-HASHES.md](BINARY-HASHES.md).

| CPU gate | Passing count |
|---|---:|
| New HC contract, six compiler settings | 4,752 |
| Fresh mini-model cases | 79 |
| Real-model cases / tokens / layer outputs | 6 / 48 / 2,304 |
| Capacity selection | 854,164 |
| Arithmetic / validation / ASAN | 22,326 / 6,899 / 3,657 |
| Fused epilogue checks / owner-lifetime suites | 56 / 18 |
| Kernel tests / memory-plan checks | 72 / 65 |
| Wrapper tests / mocked window combinations | 101 / 78 |
| Native controller cases / mailbox fault gates | 3,369 / 15 |
| Draft-capture arms / valid fixture matches | 6 / 378 |
| Cross-placement tests / pairs / semantic buffers | 11 / 3 / 17 |
| Campaign completion tests / assertions | 2 / 7 |
| Seal-binding tests / blocked-launch admission checks | 45 / 88 |

The real-model scope remains eight tokens of one fixed prompt per placement and
capacity; this is correctness evidence, not a full realistic suite or speed result.

Runtime SHA256 values after resealing:

| Build | SHA256 |
|---|---|
| gnu-host | `2416ec9c53c48d50b6fac450950162fdb480bac8c81c6f42d42177cb103d2ac4` |
| icpx-host | `bfcff86532d952549e2ccf76e2143f7b3bc0057b714daa9468e355b162d65d33` |
| asan | `2a601239a19694dcef3f3cc653ed537878301bab6c49fcc594add8490c957858` |
| device | `50381aa1220a6c6e30a597e3c0fa72d93a97453cacd96fdd833d925ac703943e` |

Build receipt SHA256: `6a54c3159392652f5fcd6befb5b1c4e647efa12e7af2d25b05dba27ab7124386`.
All five device artifact hashes changed. The runtime ABI is unchanged.
The exact before/after identities are in the qualification summary. The K1a
fixture executable is now `b09d05c1b6ef328aaa6eb4c321bc97ec37b93daf079ee410e8966ebe9b7f37a1`.


The no-launch seal rehearsal explicitly simulates a post-recovery boot, blocks
all launchers, and verifies the real fault latch stays byte-identical. Production
window admission still requires coordinator recovery; no bypass was added.

`WINDOW.md` and `coordinator_windows.sh` stay byte-identical. Sources and sealed
binary identities change: discard partial chains and start fresh after the
coordinator clears the existing latch under its recovery procedure. Neither
packet44 nor the latch is changed by this work.

## Failures, limitations and revisit conditions

The new payload gate catches five compiler configurations that the old
same-build comparison could accept. It does not emulate a GPU, qualify speed,
or certify arbitrary nonfinite behavior in unrelated operators. Keep the
unchanged-model finite-output oracle checks. Revisit on any HC payload,
control-word or compiled-source mismatch; do not normalize fixture bytes or
replace the expected result with a selected compiler's output.
