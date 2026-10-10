# Packet 137 contract

Parent: sealed packet135, manifest
`4356482eae2f1d7ac95b17e6483379ceed0cc90ed488d46765803451980402c3`.
Parent inner plan:
`7750e7b54c885f99a73ab87b17013fc0a850a1af942f0c00422adbae596258c4`.

`LTX_F32_SCAN=parent` (default) retains the parent per-word Python exponent
predicate. `bulk` uses bounded CPU byte slices and integer bit operations to
apply exactly the same exponent predicate to every original immutable F32
span, on every original call. No cache, sampling, float conversion, changed
endianness, omitted invocation, copied tensor, or numerical change is admitted.
Both paths retain the original exact-type, alignment and nonfinite errors.
The launch choice is read once at module import. Receipts and status identify
it as `server_options.f32_scan`; the status feature is `f32_scan`.

The helper is sealed in components and source/scripts. Native bindings pin its
source, module owner and function code alongside the anchor helper and refuse
substitution or changed launch mode/constants. All inherited qualification,
model, anchor, shape, hash, file-identity, memory, snapshot, storage, fault,
no-restart and deadline gates remain. Production qualification must still
compare the same eager, graph and repeat chains, every latent/image/waveform
and anchor, against the retained unchanged references.

The candidate launch remains the 145-frame split36/cone production setup.
The pure CPU predicate is valid for all inherited geometries; it does not admit
any previously refused configuration. Only bulk adds `-f32bulk` to the run name.
Off form equals135 after packet namespace and explicit option reporting are
normalized. CPU tests do not qualify device operation or prove stream speed.

The new packet preserves every changed parent byte under `provenance/packet135`.
The builder runs a sealed startup import and the complete bundled-helper import
inventory before sealing. The recursive verifier and inner-plan client pins
must pass. Run only the CPU test driver during preparation; launch instructions
are for the owner and are not part of the CPU build.
