# IQ4_NL expert-down candidates

`p29.down.wg32` assigns one subgroup of 32 lanes to one output row.
`p29.down.rows4` packs four independent rows into one 128-thread workgroup.
Both compile the production shape of 2,560 rows by 640 input elements. Each
routed slot owns a different activation vector. There is no paired down form:
down has no second matrix sharing that input.

The kernel uses the original IQ4_NL 18-byte block, with its FP16 scale followed
by 16 code bytes. The low nibbles encode elements 0–15; the high nibbles encode
16–31. The bounding study's adjacent-nibble layout is not substituted. A lane
reads the two scale bytes and converts the scale once for its eight weights;
each weight then reads a code byte and an int8 level from the 16-entry table.
Its expression stays `(scale * float(level)) * bf16_input`, accumulated in the
same eight-element lane order and 256-element tile order. The unchanged
adjacent tree reduces 32 lanes. The final K=640 tile has 16 active lanes.

The actual runtime R5 IQ4 kernel already uses byte code and level-table loads,
and converts the scale once per eight-weight decode, then uses subgroup
sharing for scale owners. This candidate removes that scale sharing, generic
format/control work and native-width numerical loop indices. It does **not**
claim that R5 performs a half conversion per weight or 64-bit IQ4 table loads.
Source indices are unsigned 32-bit; even expert 511 ends below 472 MB. Native
pointer addressing remains native-width. There are no barriers or local memory
allocations in either new kernel body; subgroup exchange appears only in the
unchanged final sum tree, never for decoding a weight.

The host validator admits either the full 512-expert bank or the runtime's
streamed ten-expert bank. It binds that actual bank size into the kernel, so
invalid compact routes cannot reach outside allocated weights. Other checks
are shared with packet28: BF16 inputs/outputs, ten routes, full row span,
separate outputs/status, no aliasing, aligned device allocations, complete
weight extents and preallocated scratch. The compact-bank allowance is the
only validation-contract expansion relative to packet28. Original packet28
kernels and their numerical arguments are preserved; their host emulation adds
only two-thread row parallelism.

No device binary has been run by this worker. No performance improvement is
claimed. K2 selects only after exact byte equality and an independently timed
rotated-buffer median below 0.9 times the incumbent.
