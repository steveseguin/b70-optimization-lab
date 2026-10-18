# Production lookup mechanism and exact alternatives

The source base is packet97, with the production expert path inherited from
packet65 through packets84/91. `parent-source-manifest.json` pins the frozen
inputs; the new binary rebuilds entry/main, dispatch and expert submission and
hash-checks the remaining packet97 objects.

## Gate/up: IQ2_S

`p65_expert.hpp::wide_chains` reads four contiguous uint32 code words for each
physical lane, plus two high-index bytes, two scale bytes and the block's FP16
scale. Four physical lanes cover the 32 logical FP32 chains for each row.
Each physical lane owns eight independent sums. A WG64 contains two SG32s,
one for gate and one for up, processing eight row pairs.

For each eight-weight tile at `k`, `q=(k%256)/8`:

```
index = (code_and_signs & 255) | (((high >> (2*(q%4))) & 3) << 8)
signs = code_and_signs >> 8
a = iq2_words[2*index]
b = iq2_words[2*index+1]
magnitude[j] = ((j<4 ? a : b) >> (8*(j%4))) & 255
```

The 1,024-entry grid is 8,192 bytes. C++ declares it `inline constexpr`;
the actual linked IR declares **address-space 1 global constant data**, and
linked BMG assembly issues `load.ugm.d32x2.a64`. It is neither SLM nor a
subgroup-register table. There is **no sign-table lookup** on this IQ2_S path:
the eight sign bits are inline in the packed weight code. Each is used to
negate an integer magnitude before the FP32 scale multiply, with the original
two-multiply exceptional path for NaN/Inf scales.

There are 32 logical grid entries per 256-weight block per matrix row: two
uint32 source accesses, normally one d32x2 message, per eight weights. There
are no dependent table loads per individual weight. For K=2560, that is 320
entries per row, 80 per physical lane. Full gate/up has 6,400 rows per stream,
or 4,096,000 logical grid-entry reads across both streams. These are logical
reads, not physical DRAM transactions; cache may satisfy them.

The dependency is packed-code/high load → index extraction → indexed grid
load → magnitude/sign decode → FP32 weight → product. Packet86's constant-grid
ablation removes the indexed read and its dependency. Its supplied rank1
1.50→0.92 ms difference is consistent with this critical path. It is a
non-exact diagnostic, not proof that 0.58 ms is recoverable by an exact kernel:
constant propagation also changes compiler scheduling and decode work. Do not
add diagnostic differences or treat the projected +1.7 tok/s as measured.

## Down: IQ4_NL

Down is K=640, 2,560 output rows per selected expert, twenty 32-weight blocks.
Each block contains sixteen code bytes and one FP16 scale. The low/high nibble
selects one of `{-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113}`.
`p33::level_bank` selects among four immediate uint32 banks, extracts a signed
byte, converts to FP32 and multiplies by the scale. There is **no IQ2 grid and
no global IQ4 level-table read** in production. Its decode work is nibble
extraction, register-bank selection, signed conversion and scale conversion/
multiplication. The diagnostic 0.43 ms difference does not isolate their costs.

The exact byte-pair SLM alternative is retained but rejected: linked code
spills 1,664 bytes with 52 scratch messages. It gets no micro job or screen.
See [down closeout](DOWN-CLOSEOUT.md).

## Linked offline checks

`register-report-offline.json` binds linked compiler commands, dependencies,
compressed native assembly and vISA. All kernels use 128 configured GRFs.
Counts below are static instructions, not time predictions.

| IQ2 view | Lookup | Instructions | Scratch spills |
| --- | --- | ---: | ---: |
| production wide64 | global d32x2 | 1993 | 0 |
| exp-slm | SLM d32x2; 8 KiB fill | 1840 | 0 |
| exp-slm+halfcache | SLM d32x2 | 1791 | 0 |
| exp-compact-slm | SLM d32; 2 KiB fill | 2308 | 0 |
| exp-compact-slm+halfcache | SLM d32 | 2260 | 0 |
| exp-compact-global | global d32; 2 KiB table | 2323 | 0 |
| exp-compact-global+halfcache | global d32 | 2271 | 0 |

Each SLM kernel fills cooperatively once per workgroup and all 64 threads
barrier before any invalid-route branch. Compact entries reconstruct the exact
integer magnitudes 8, 25 or 43; packed lookup representation does not alter
model precision. The global compact candidate deliberately retains the global
address space; the proven change is table footprint and read width. The 16-bit
KV cache and all FP32 accumulation order remain unchanged.

Packet52 already tried this compact magnitude encoding, with a different
arithmetic/geometry. Its source stages 2 KiB despite an older note saying 8 KiB.
Packet99 reuses that lab technique under exact production wide64 arithmetic,
paired word storage and packet86's new evidence. Neither improved amortization
nor a novel compact encoding is claimed. Only measured kernel timing can reopen
the SLM lever for model screens.
