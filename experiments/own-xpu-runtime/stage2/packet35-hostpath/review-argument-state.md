# Host argument-state audit

The CPU audit serializes the full runtime state of the 14 host operation types
in `argument-state-registry.json`. The reviewed fields are:

| Operation family | Runtime members |
| --- | --- |
| Dense and expert host multiply | matrices, variant, shared |
| Mixture combine | rows |
| p25/p27 GEMV | host |
| p27 input conversion | n |
| p28 GEMV | b |
| p29 expert down | experts |
| Small GEMV tuple | none; type identifies compile-time tuple |
| Specialised non-GEMV | shape |
| Round2 non-GEMV and simple operators | s |
| Packet18 simple operators | spec, work |
| Packet18 non-GEMV host operation | shape |
| Packet18 glue, including checks and commits | s, mode |
| Serial step fallback | spec |

The type name binds compile-time operation, phase, split, width and template
arguments. The complete scalar structs (`Spec`, shape and GEMV bound state)
are trivially copyable. The audit copies them, clears ABI padding with GCC's
`__builtin_clear_padding`, and records the remaining bytes. Matrix vectors
record their length and every matrix's complete value. This never changes the
live operation or arithmetic. Device records separately bind allocation IDs,
extents and pointers.

`argument_block_test.cpp` verifies equality across deliberately different
padding, scalar/member/vector changes, an unchanged copied operation, empty
operation identity, and rejection of unknown stateful operation types. Its
nine checks run only on the CPU. Non-GCC audit requests fail explicitly;
ordinary non-audit builds remain valid.

C++20 does not expose member reflection. This is a reviewed member registry,
not a claim to discover future members automatically. `argument_state_gate.py`
hash-binds the nine complete operation source files and fails on any change
until their member inventory is reviewed again. It also checks every registered
member has a serializer entry. An operation with no recognized state member fails the audit. A new operation
that reuses a recognized member name still needs registry review; the serializer
does not infer its other fields.

A byte-for-byte CPU argument block comparison proves preparation retained the
registered state. The independent ELF proof establishes the compiled device
kernel identity; CPU argument logs alone do not prove native driver submission
or device execution.
