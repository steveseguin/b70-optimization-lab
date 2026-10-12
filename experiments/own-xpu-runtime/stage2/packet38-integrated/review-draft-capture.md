# Independent draft capture review

Reviewed `argument_block.hpp` against the complete instance members of
`mtp_kernels.cpp` and `p30_submit.cpp` after resident argument auditing found
unregistered draft operations. Dense stores `Linear a`; its complete trivially
copyable object is now captured with padding cleared. Merge stores `width`;
that field is now captured. Norm has no instance members and its template
width/stage are bound by the captured type identity. Elements stores `s`,
already covered. Packet 30 Attention stores `shape` and `variant`, both covered.
Small stores `family`, `metadata`, and `count`; all three are now covered.
String/vector content is serialized rather than object pointer bookkeeping.
Bound allocation IDs and pointer arrays are retained separately by Device.
No missing operation data member was found in these added paths.

`prepared_invalidation_test.cpp` adds an explicit negative gate: releasing
unrelated draft scratch advances the shared owner's generation and rejects an
otherwise live target capture. The positive gate retains scratch through four
in-place request resets and provider-view destruction; target capture remains
valid with unchanged bytes and owner generation. These augment the actual
resident Engine/provider reset and native-controller gates. DraftRuntime has
no destructor that releases Engine allocations; Engine owns their shutdown.
No device was used for this review.
